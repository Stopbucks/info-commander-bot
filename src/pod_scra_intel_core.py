

# ---------------------------------------------------------
# src/pod_scra_intel_core.py v2.1  (卸除boto3)
# 任務：1. 階梯式任務發動 2. 記憶體強制回收 3. API 重試邏輯
# ---------------------------------------------------------
import os, requests, json, time, random, base64, re, gc
from datetime import datetime, timezone
from supabase import create_client
from src.pod_scra_intel_trans import compress_task_to_opus

def get_secrets():
    return {
        "SB_URL": os.environ.get("SUPABASE_URL"),
        "SB_KEY": os.environ.get("SUPABASE_KEY"),
        "GROQ_KEY": os.environ.get("GROQ_API_KEY"),
        "GEMINI_KEY": os.environ.get("GEMINI_API_KEY"),
        "TG_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN"),
        "TG_CHAT": os.environ.get("TELEGRAM_CHAT_ID"),
        "R2_URL": os.environ.get("R2_PUBLIC_URL")
    }

def get_sb():
    s = get_secrets()
    return create_client(s["SB_URL"], s["SB_KEY"])

def parse_intel_metrics(text):
    """從 AI 文本中提取量化指標"""
    metrics = {"score": 0, "stated": 0, "inferred": 0, "subjective": 0, "evidence": 0}
    try:
        s_match = re.search(r"綜合情報分.*?(\d+)", text)
        if s_match: metrics["score"] = int(s_match.group(1))
        e_match = re.search(r"關鍵實證數：(\d+)", text)
        if e_match: metrics["evidence"] = int(e_match.group(1))
        v_match = re.findall(r": (\d+) 分", text)
        if len(v_match) >= 3:
            metrics["stated"], metrics["inferred"], metrics["subjective"] = map(int, v_match[:3])
    except: pass
    return metrics

# =========================================================
# 🎤 第一棒：Audio to STT (產線調度官 - 偵查碼加強版)
# =========================================================
def run_audio_to_stt_mission():
    """🧠 情報官大腦：只負責決策與 AI 調度"""
    sb = get_sb(); s = get_secrets()
    worker_id = os.environ.get("WORKER_ID", "UNKNOWN")
    mem_tier = int(os.environ.get("MEMORY_TIER", 256)) 
    
    # 領料判定 (大件優先/分流)
    sort_desc = (mem_tier >= 512)
    res = sb.table("mission_queue").select("*")\
            .eq("scrape_status", "completed").is_("skip_reason", "null")\
            .order("audio_size_mb", desc=sort_desc).limit(2 if sort_desc else 1).execute()

    for task in (res.data or []):
        r2_url = task.get('r2_url', '').lower()
        
        # --- 決策分歧點 ---
        if mem_tier >= 512 and r2_url.endswith('.mp3'):
            # 🚀 呼叫運輸官執行壓縮任務
            print(f"📡 [情報官] 下令物流站進行物資壓縮: {task['id'][:8]}")
            success, new_url = compress_task_to_opus(task['id'], task['r2_url'])
            if success:
                sb.table("mission_queue").update({
                    "r2_url": new_url, "audio_ext": ".opus", "used_provider": f"{worker_id}_L-OPT"
                }).eq("id", task['id']).execute()
            continue 

        # --- 正常 AI 轉譯流程 ---
        try:
            if chosen_provider == "GROQ":
                audio_url = f"{s['R2_URL']}/{task['r2_url']}"
                print(f"📥 [第一棒偵查] GROQ 模式：從 R2 下載音檔進行轉譯... URL: {audio_url}")
                audio_data = requests.get(audio_url, timeout=60).content
                time.sleep(1.5)

                headers = {"Authorization": f"Bearer {s['GROQ_KEY']}"}
                files = {'file': (task['r2_url'], audio_data, 'audio/mpeg')}
                data = {'model': 'whisper-large-v3', 'response_format': 'text', 'language': 'en'}
                
                print(f"🎙️ [第一棒偵查] 送往 Groq Whisper 模型...")
                stt_resp = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", 
                                         headers=headers, files=files, data=data, timeout=120)
                
                if stt_resp.status_code == 200:
                    sb.table("mission_intel").update({
                        "stt_text": stt_resp.text, "intel_status": "Sum.-pre"
                    }).eq("task_id", task_id).execute()
                    print(f"✅ [第一棒偵查] Groq Whisper 轉譯成功！")
                else:
                    # 🚀 關鍵修正：此處會印出 Groq 官方的詳細報錯原因
                    print(f"❌ [第一棒偵查] Groq Whisper 失敗！狀態碼: {stt_resp.status_code}")
                    print(f"📑 [報錯細節]: {stt_resp.text}") 
                    raise Exception(f"Whisper Fail: {stt_resp.status_code}")
                
                del audio_data; gc.collect()

            else:
                # GEMINI 路徑 (不在此執行轉譯，僅標記)
                sb.table("mission_intel").update({
                    "stt_text": "[GEMINI_2.5_NATIVE_STREAM]", "intel_status": "Sum.-pre"
                }).eq("task_id", task_id).execute()
                print(f"✅ [第一棒偵查] GEMINI 原生流已鎖定。")

        except Exception as e:
            print(f"💥 [第一棒偵查] 任務崩潰: {str(e)}")
            # 發生異常則退回，刪除進度讓下次重來
            sb.table("mission_intel").delete().eq("task_id", task_id).execute()
            print(f"🛡️ [第一棒偵查] 已刪除任務記錄，系統將自動重啟此任務。")


# =========================================================
# ✍️ 第二棒：STT to Summary (情報精煉官 - 偵查碼加強版)
# =========================================================
def run_stt_to_summary_mission():
    # 戰術延遲：防止多節點併發搶佔
    time.sleep(random.uniform(3.0, 8.0))
    sb = get_sb(); s = get_secrets()
    
    # 1. 偵查待處理物資
    #  🚀 文字組處理數量修改區域 
    res = sb.table("mission_intel").select("*, mission_queue(episode_title, source_name, r2_url)")\
            .eq("intel_status", "Sum.-pre").limit(2).execute()
    
    #  🚀 文字組 
    #---文字組處理數量修改區域 

    if not res.data:
        print("☕ [偵查] 目前資料庫暫無待摘要物資 (Sum.-pre)，哨所待命。")
        return

    for intel in (res.data or []):
        task_id = intel['task_id']
        title = intel['mission_queue']['episode_title']
        print(f"📡 [偵查] 啟動摘要任務 ID: {task_id[:8]} | 標題: {title[:20]}...")
        
        p_res = sb.table("pod_scra_metadata").select("content").eq("key_name", "PROMPT_FALLBACK").single().execute()
        sys_prompt = p_res.data['content'] if p_res.data else "請分析情報。"

        try:
            summary = ""
            provider = intel['ai_provider']
            print(f"🤖 [偵查] 目前指定 AI 供應商: {provider}")

            # 分流處理 A: GROQ
            if provider == "GROQ":
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "system", "content": sys_prompt},
                                 {"role": "user", "content": f"分析逐字稿：\n\n{intel['stt_text'][:50000]}"}],
                    "temperature": 0.3
                }
                ai_resp = requests.post("https://api.groq.com/openai/v1/chat/completions", 
                                        headers={"Authorization": f"Bearer {s['GROQ_KEY']}"}, json=payload, timeout=90)
                if ai_resp.status_code == 200:
                    summary = ai_resp.json()['choices'][0]['message']['content']
                    print(f"✅ [偵查] GROQ 摘要生成成功，長度: {len(summary)}")
                else:
                    print(f"❌ [偵查] GROQ API 報錯: {ai_resp.status_code} | 回應: {ai_resp.text}")

            # 分流處理 B: GEMINI
            # --- 修正後的 GEMINI 處理區塊 ---
            elif provider == "GEMINI":

                audio_url = f"{s['R2_URL']}/{intel['mission_queue']['r2_url']}"
                print(f"📥 [偵查] 下載音檔至內存執行原生流... URL: {audio_url}")
                raw_bytes = requests.get(audio_url, timeout=120).content
                
                # 🚀 第一次清理：轉換完 Base64 立即釋放原始字節
                b64_audio = base64.b64encode(raw_bytes).decode('utf-8')
                del raw_bytes 
                gc.collect() 

                # 準備發送到 Gemini
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={s['GEMINI_KEY']}"
                payload = {
                    "contents": [{"parts": [{"text": sys_prompt},
                                            {"inline_data": {"mime_type": "audio/mpeg", "data": b64_audio}}]}]
                }
                
                # 🚀 核心動作：發送請求
                ai_resp = requests.post(gemini_url, json=payload, timeout=180)
                
                if ai_resp.status_code == 200:
                    summary = ai_resp.json()['candidates'][0]['content']['parts'][0]['text']
                    print(f"✅ [偵查] GEMINI 摘要生成成功，長度: {len(summary)}")
                else:
                    print(f"❌ [偵查] GEMINI API 報錯: {ai_resp.status_code} | 回應: {ai_resp.text}")

                # 🚀 第二次清理：收到回應後立即釋放龐大的 Base64 字串
                del b64_audio
                gc.collect()
            # 2. 成果入庫與 Telegram 通報
            if summary:
                m = parse_intel_metrics(summary)
                sb.table("mission_intel").update({
                    "summary_text": summary, "intel_status": "Sum.-ready",
                    "report_date": datetime.now().strftime("%Y-%m-%d"),
                    "total_score": m["score"], "evidence_count": m["evidence"]
                }).eq("task_id", task_id).execute()
                print("💾 [偵查] 摘要已安全存入資料庫，狀態更新為 Sum.-ready")
                
                # --- 🔍 核心偵查點：Telegram 金鑰與環境變數檢查 ---
                if not s["TG_TOKEN"] or not s["TG_CHAT"]:
                    print("⚠️ [偵查] 警報：環境變數中找不到 TG_TOKEN 或 TG_CHAT，放棄發送！")
                else:
                    print(f"📤 [偵查] 準備發送 Telegram 訊息至 Chat ID: {s['TG_CHAT']}...")
                    time.sleep(1.5)
                    report_msg = f"🎙️ {intel['mission_queue']['source_name']}\n📌 {intel['mission_queue']['episode_title']}\n\n{summary}"
                    tg_resp = requests.post(f"https://api.telegram.org/bot{s['TG_TOKEN']}/sendMessage", 
                                            json={"chat_id": s["TG_CHAT"], "text": report_msg[:4000], "parse_mode": "Markdown"})
                    
                    if tg_resp.status_code == 200:
                        sb.table("mission_intel").update({"intel_status": "Sum.-sent"}).eq("task_id", task_id).execute()
                        print(f"🎉 [偵查] Telegram 通報成功！任務結案。")
                    else:
                        print(f"❌ [偵查] Telegram 通報失敗！代碼: {tg_resp.status_code} | 回應: {tg_resp.text}")
            else:
                print("⚠️ [偵查] 摘要內容為空，跳過存檔與通報程序。")

        except Exception as e:
            print(f"💥 [偵查] 任務執行中崩潰: {str(e)}")
            import traceback
            print(traceback.format_exc()) # 噴出完整錯誤堆疊以便定位

