# ---------------------------------------------------------
# src/pod_scra_intel_core.py v4.6 (RENDER / KOYEB 雙擎防護版)
# 任務：1. 分流決策 2. STT 轉譯 3. 情報摘要
# 修正：導入先結案後發報機制、防禦 Duplicate Key 崩潰
# ---------------------------------------------------------

import os, requests, json, time, random, base64, re, gc
from datetime import datetime, timezone
from src.pod_scra_intel_r2 import compress_task_to_opus
from src.pod_scra_intel_groqcore import GroqFallbackAgent

def get_secrets():
    """集中管理所有外部金鑰"""
    return {
        "SB_URL": os.environ.get("SUPABASE_URL"), "SB_KEY": os.environ.get("SUPABASE_KEY"),
        "GROQ_KEY": os.environ.get("GROQ_API_KEY"), "GEMINI_KEY": os.environ.get("GEMINI_API_KEY"),
        "TG_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN"), "TG_CHAT": os.environ.get("TELEGRAM_CHAT_ID"),
        "R2_URL": os.environ.get("R2_PUBLIC_URL")
    }

def parse_intel_metrics(text):
    """解析情報評分指標"""
    metrics = {"score": 0, "evidence": 0}
    try:
        s_match = re.search(r"綜合情報分.*?(\d+)", text)
        if s_match: metrics["score"] = int(s_match.group(1))
    except: pass
    return metrics

# =========================================================
# 🎤 第一棒：Audio to STT (搭載戰場觀測儀版)
# =========================================================
def run_audio_to_stt_mission(sb): 
    """負責物資分流與轉譯啟動"""
    s = get_secrets()
    worker_id = os.environ.get("WORKER_ID", "UNKNOWN")
    mem_tier = int(os.environ.get("MEMORY_TIER", 256)) 
    sort_desc = (mem_tier >= 512)
    
    print(f"🔍 [{worker_id}] 正在搜尋 STT 任務... (本機記憶體體量: {mem_tier}MB)")
    res = sb.table("view_worker_task_inbox").select("*").order("audio_size_mb", desc=sort_desc).limit(1).execute()

    if not res.data: 
        print(f"☕ [{worker_id}] 目前沒有需要 STT 的任務。")
        return
        
    for task in res.data:
        task_id = task['id']
        r2_url = task.get('r2_url', '').lower()
        print(f"🎯 [{worker_id}] 鎖定目標: {task['source_name']} (格式: {r2_url[-4:]})")
        
        try:
            # 🚀 鋼鐵加固 1：檢查是否已存在，若存在且卡住，不可重新 Insert！
            check = sb.table("mission_intel").select("intel_status").eq("task_id", task_id).execute()
            if check.data:
                status = check.data[0].get('intel_status')
                print(f"⚠️ [{worker_id}] 發現任務已存在 mission_intel (狀態: {status})，跳過初始化。")
                continue

            # --- 🛠️ 階段 A：512MB 窄化壓縮 ---
            if mem_tier >= 512 and (r2_url.endswith('.mp3') or r2_url.endswith('.m4a')):
                print(f"⚙️ [{worker_id}] 啟動 FFmpeg 壓縮引擎...")
                success, new_url = compress_task_to_opus(task_id, task['r2_url'])
                if success:
                    print(f"✅ [{worker_id}] 壓縮成功，新檔名: {new_url}。將直接進入 AI 轉譯！")
                    sb.table("mission_queue").update({"r2_url": new_url, "audio_ext": ".opus"}).eq("id", task_id).execute()
                    r2_url = new_url
                    task['r2_url'] = new_url
                else:
                    print(f"❌ [{worker_id}] 壓縮失敗，放棄此任務。")
                    continue

            # --- 🛠️ 階段 B：迴避機制 ---
            if mem_tier < 512 and (r2_url.endswith('.mp3') or r2_url.endswith('.m4a')): 
                print(f"🛡️ [{worker_id}] 體量不足，主動迴避巨大檔案，讓重裝部隊處理。")
                continue

            # --- 🛠️ 階段 C：AI 轉譯分流 ---
            chosen_provider = random.choice(["GROQ", "GEMINI"])
            print(f"🧠 [{worker_id}] 進入 AI 轉譯階段，抽籤決定使用: {chosen_provider}")
            
            sb.table("mission_intel").insert({"task_id": task_id, "intel_status": "Sum.-proc", "ai_provider": chosen_provider}).execute()

            if chosen_provider == "GROQ":
                print(f"🚀 [{worker_id}] 準備發送音檔至 Groq API...")
                m_type = "audio/ogg" if ".opus" in r2_url else "audio/mpeg"
                
                print(f"📥 [{worker_id}] 從 R2 緩存音檔: {s['R2_URL']}/{task['r2_url']}")
                audio_response = requests.get(f"{s['R2_URL']}/{task['r2_url']}", timeout=60)
                audio_response.raise_for_status() 
                audio_data = audio_response.content
                
                print(f"📤 [{worker_id}] 發送給 Groq Whisper 模型...")
                stt_resp = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", 
                    headers={"Authorization": f"Bearer {s['GROQ_KEY']}"},
                    files={'file': (task['r2_url'], audio_data, m_type)},
                    data={'model': 'whisper-large-v3', 'response_format': 'text', 'language': 'en'}, timeout=120)
                    
                if stt_resp.status_code == 200:
                    print(f"🎉 [{worker_id}] Groq 轉寫成功！寫入資料庫...")
                    sb.table("mission_intel").update({"stt_text": stt_resp.text, "intel_status": "Sum.-pre"}).eq("task_id", task_id).execute()
                else:
                    print(f"💥 [{worker_id}] Groq 轉寫失敗 (HTTP {stt_resp.status_code}): {stt_resp.text}")
                    sb.table("mission_intel").delete().eq("task_id", task_id).execute() # 失敗則清空重來
                    raise Exception(f"Groq API Error: {stt_resp.status_code}")
                    
                del audio_data; gc.collect()
            else:
                print(f"🤖 [{worker_id}] 選擇 Gemini 流水線，先掛上代位符...")
                sb.table("mission_intel").update({"stt_text": "[GEMINI_2.5_NATIVE_STREAM]", "intel_status": "Sum.-pre"}).eq("task_id", task_id).execute()
                
        except Exception as e:
            print(f"💥 [{worker_id}] [加工中斷嚴重錯誤]: {str(e)}")
            
        time.sleep(15); gc.collect()

# =========================================================
# ✍️ 第二棒：STT to Summary 
# =========================================================
def run_stt_to_summary_mission(sb): 
    """讀取 STT 結果產出摘要"""
    time.sleep(random.uniform(3.0, 8.0)); s = get_secrets()
    worker_id = os.environ.get("WORKER_ID", "UNKNOWN")
    
    res = sb.table("mission_intel").select("*, mission_queue(*)").eq("intel_status", "Sum.-pre").limit(1).execute()
    if not res.data: return
    for intel in res.data:
        task_id = intel['task_id']; provider = intel['ai_provider']; q_data = intel.get('mission_queue') or {}
        print(f"✍️ [{worker_id}] 啟動摘要產線: {provider} | 任務: {q_data.get('episode_title', '未知')[:15]}...")

        try:
            summary = ""; p_meta = sb.table("pod_scra_metadata").select("content").eq("key_name", "PROMPT_FALLBACK").single().execute()
            sys_prompt = p_meta.data['content'] if p_meta.data else "分析情報。"

            if provider == "GROQ":
                print(f"🛡️ [{worker_id}] 防爆啟動：委託 GroqFallbackAgent 處理長文本...")
                groq_agent = GroqFallbackAgent()
                summary = groq_agent.generate_summary(intel['stt_text'], sys_prompt)

            elif provider == "GEMINI":
                a_url = f"{s['R2_URL']}/{q_data.get('r2_url', '')}"; m_type = "audio/ogg" if ".opus" in a_url.lower() or ".ogg" in a_url.lower() else "audio/mpeg"
                print(f"📥 [{worker_id}] GEMINI 模式：下載物資... URL: {a_url}")
                raw_bytes = requests.get(a_url, timeout=120).content
                b64_audio = base64.b64encode(raw_bytes).decode('utf-8'); del raw_bytes; gc.collect()
                
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={s['GEMINI_KEY']}"
                payload = {"contents": [{"parts": [{"text": sys_prompt}, {"inline_data": {"mime_type": m_type, "data": b64_audio}}]}]}
                
                print(f"📤 [{worker_id}] 發送給 Gemini 模型...")
                ai_resp = requests.post(g_url, json=payload, timeout=180)
                if ai_resp.status_code == 200:
                    cands = ai_resp.json().get('candidates', [])
                    if cands and cands[0].get('content'): summary = cands[0]['content']['parts'][0].get('text', "")
                else:
                    print(f"💥 [{worker_id}] Gemini 摘要失敗 (HTTP {ai_resp.status_code})")
                del b64_audio; gc.collect()

            if summary:
                m = parse_intel_metrics(summary)
                
                # 🚀 鋼鐵加固 2：先更新資料庫，確保任務結案 (先上車後補票)
                sb.table("mission_intel").update({
                    "summary_text": summary, 
                    "intel_status": "Sum.-sent", # ✅ 結案！
                    "report_date": datetime.now().strftime("%Y-%m-%d"), 
                    "total_score": m["score"]
                }).eq("task_id", task_id).execute()
                print(f"💾 [{worker_id}] 摘要已安全存入資料庫，狀態更新為 Sum.-sent。")

                # 🚀 獨立的 Telegram 發送區塊，失敗不影響大局
                try:
                    report_msg = f"🎙️ {q_data.get('source_name', '未知來源')}\n📌 {q_data.get('episode_title', '未知標題')}\n\n{summary}"
                    tg_resp = requests.post(f"https://api.telegram.org/bot{s['TG_TOKEN']}/sendMessage", 
                                            json={"chat_id": s["TG_CHAT"], "text": report_msg[:4000], "parse_mode": "Markdown"},
                                            timeout=15)
                    if tg_resp.status_code == 200:
                        print(f"🎉 [{worker_id}] 戰報發送成功。")
                    else:
                        print(f"⚠️ [{worker_id}] 戰報發送遭拒: {tg_resp.status_code}")
                except Exception as tg_e:
                    print(f"⚠️ [{worker_id}] TG 網路中斷，但不影響資料庫結案: {tg_e}")

        except Exception as e: print(f"💥 [{worker_id}] 摘要階段異常: {e}")