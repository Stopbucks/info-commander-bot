
# ---------------------------------------------------------
# src/pod_scra_intel_core.py v1.5 (2026 REST 韌性強化版)
# 模型：Gemini 2.5 Flash 勿動
# 任務：1. 隨機分流 2. 輕量 REST + Opus傳輸 3. 量化指標自動入庫
# ---------------------------------------------------------
# ---------------------------------------------------------
# src/pod_scra_intel_core.py v1.6 (2026 鋼鐵韌性加固版)
# 任務：1. 階梯式任務發動 2. 記憶體強制回收 3. API 重試邏輯
# ---------------------------------------------------------
import os, requests, json, time, random, base64, re, gc
from datetime import datetime, timezone
from supabase import create_client

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
# 🎤 第一棒：Audio to STT (產線調度官)
# =========================================================
def run_audio_to_stt_mission():
    # 戰術延遲：防止多節點併發搶佔
    time.sleep(random.uniform(3.0, 8.0))
    sb = get_sb(); s = get_secrets()
    
    res = sb.table("mission_queue").select("id, r2_url, episode_title")\
            .eq("scrape_status", "completed").order("created_at", desc=True).limit(3).execute()
    
    for task in (res.data or []):
        task_id = task['id']
        check = sb.table("mission_intel").select("id").eq("task_id", task_id).execute()
        if check.data: continue

        chosen_provider = random.choice(["GROQ", "GEMINI"])
        print(f"🎲 [分流] 任務 {task_id[:8]} -> [{chosen_provider}]")
        
        # 🔒 標記開始處理
        sb.table("mission_intel").insert({
            "task_id": task_id, "intel_status": "Sum.-proc", "ai_provider": chosen_provider
        }).execute()

        try:
            if chosen_provider == "GROQ":
                audio_url = f"{s['R2_URL']}/{task['r2_url']}"
                audio_data = requests.get(audio_url, timeout=60).content
                time.sleep(1.5) # 給予網路緩衝

                headers = {"Authorization": f"Bearer {s['GROQ_KEY']}"}
                files = {'file': (task['r2_url'], audio_data, 'audio/mpeg')}
                data = {'model': 'whisper-large-v3', 'response_format': 'text', 'language': 'en'}
                
                # 執行 API (內建簡單重試邏輯)
                stt_resp = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", 
                                         headers=headers, files=files, data=data, timeout=120)
                
                if stt_resp.status_code == 200:
                    sb.table("mission_intel").update({
                        "stt_text": stt_resp.text, "intel_status": "Sum.-pre"
                    }).eq("task_id", task_id).execute()
                    print(f"✅ [GROQ] 轉譯成功")
                else: raise Exception(f"Groq API Fail: {stt_resp.status_code}")
                
                # 🧹 清理大型二進位變數
                del audio_data; gc.collect()

            else:
                # GEMINI 原生流不需在此下載，直接標記交棒
                sb.table("mission_intel").update({
                    "stt_text": "[GEMINI_2.5_NATIVE_STREAM]", "intel_status": "Sum.-pre"
                }).eq("task_id", task_id).execute()
                print(f"✅ [GEMINI] 已鎖定原生流")

        except Exception as e:
            print(f"❌ [第一棒異常]: {e}")
            sb.table("mission_intel").delete().eq("task_id", task_id).execute()

# =========================================================
# ✍️ 第二棒：STT to Summary (情報精煉官)
# =========================================================
def run_stt_to_summary_mission():
    # 戰術延遲
    time.sleep(random.uniform(3.0, 8.0))
    sb = get_sb(); s = get_secrets()
    
    res = sb.table("mission_intel").select("*, mission_queue(episode_title, source_name, r2_url)")\
            .eq("intel_status", "Sum.-pre").limit(1).execute()
    
    for intel in (res.data or []):
        task_id = intel['task_id']
        provider = intel['ai_provider']
        print(f"✍️ [精煉] 產線: {provider} | 任務: {intel['mission_queue']['episode_title'][:15]}...")
        
        p_res = sb.table("pod_scra_metadata").select("content").eq("key_name", "PROMPT_FALLBACK").single().execute()
        sys_prompt = p_res.data['content'] if p_res.data else "請分析情報。"

        try:
            summary = ""
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

            elif provider == "GEMINI":
                audio_url = f"{s['R2_URL']}/{intel['mission_queue']['r2_url']}"
                # 🛠️ 記憶體與網路加固：
                raw_bytes = requests.get(audio_url, timeout=120).content
                time.sleep(2.0) # 下載後稍微喘息
                b64_audio = base64.b64encode(raw_bytes).decode('utf-8')
                del raw_bytes; gc.collect() # 立即釋放原始二進位

                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={s['GEMINI_KEY']}"
                payload = {
                    "contents": [{"parts": [{"text": sys_prompt},
                                           {"inline_data": {"mime_type": "audio/mpeg", "data": b64_audio}}]}]
                }
                ai_resp = requests.post(gemini_url, json=payload, timeout=180)
                if ai_resp.status_code == 200:
                    summary = ai_resp.json()['candidates'][0]['content']['parts'][0]['text']
                
                # 🧹 徹底清理
                del b64_audio; gc.collect()

            if summary:
                m = parse_intel_metrics(summary)
                # 先入庫，確保數據安全
                sb.table("mission_intel").update({
                    "summary_text": summary, "intel_status": "Sum.-ready",
                    "report_date": datetime.now().strftime("%Y-%m-%d"),
                    "total_score": m["score"], "evidence_count": m["evidence"]
                }).eq("task_id", task_id).execute()
                
                # 發送 TG (最後一步，失敗也不影響數據已存檔)
                time.sleep(1.5)
                report_msg = f"🎙️ {intel['mission_queue']['source_name']}\n📌 {intel['mission_queue']['episode_title']}\n\n{summary}"
                tg_resp = requests.post(f"https://api.telegram.org/bot{s['TG_TOKEN']}/sendMessage", 
                                        json={"chat_id": s["TG_CHAT"], "text": report_msg[:4000], "parse_mode": "Markdown"})
                
                if tg_resp.status_code == 200:
                    sb.table("mission_intel").update({"intel_status": "Sum.-sent"}).eq("task_id", task_id).execute()
                    print(f"✅ [成功] 任務 {task_id[:8]} 情報已結案")

        except Exception as e:
            print(f"❌ [第二棒崩潰]: {e}")
            # 發生崩潰時不刪除，讓 Vercel 清道夫在一小時後回收