

# ---------------------------------------------------------
# src/pod_scra_intel_core.py v4.2.1  (卸除boto3 版本序號對齊)
# 任務：1. 階梯式任務發動 2. 記憶體強制回收 3. API 重試邏輯
# 修改：GEMINI 對opus MIME 類型判斷 ，處理 NameError
# ---------------------------------------------------------

import os, requests, json, time, random, base64, re, gc
from datetime import datetime, timezone
from supabase import create_client
from src.pod_scra_intel_trans import compress_task_to_opus

# ... (get_secrets, get_sb, parse_intel_metrics 保持不變) ...

# =========================================================
# 🎤 第一棒：Audio to STT (決策中樞 - 防崩潰強化)
# =========================================================
def run_audio_to_stt_mission():
    sb = get_sb(); s = get_secrets()
    worker_id = os.environ.get("WORKER_ID", "UNKNOWN")
    mem_tier = int(os.environ.get("MEMORY_TIER", 256)) 
    
    sort_desc = (mem_tier >= 512)
    res = sb.table("mission_queue").select("*")\
            .eq("scrape_status", "completed").is_("skip_reason", "null")\
            .order("audio_size_mb", desc=sort_desc).limit(2 if sort_desc else 1).execute()

    if not res.data:
        return

    for task in res.data:
        task_id = task['id']
        r2_url = task.get('r2_url', '').lower()

        try:
            # 🚀 A：512MB 專屬 MP3 壓縮
            if mem_tier >= 512 and r2_url.endswith('.mp3'):
                print(f"📡 [{worker_id}] 偵測到 MP3，啟動改裝流程...")
                success, new_url = compress_task_to_opus(task_id, task['r2_url'])
                if success:
                    sb.table("mission_queue").update({
                        "r2_url": new_url, "audio_ext": ".opus", "used_provider": f"{worker_id}_L-OPT"
                    }).eq("id", task_id).execute()
                continue 

            # 🚀 B：AI 轉譯
            if mem_tier < 512 and r2_url.endswith('.mp3'):
                continue # 256MB 跳過 MP3

            check = sb.table("mission_intel").select("id").eq("task_id", task_id).execute()
            if check.data: continue

            chosen_provider = random.choice(["GROQ", "GEMINI"])
            print(f"🎲 [{worker_id}] 分流決策: [{chosen_provider}]")
            
            sb.table("mission_intel").insert({
                "task_id": task_id, "intel_status": "Sum.-proc", "ai_provider": chosen_provider
            }).execute()

            if chosen_provider == "GROQ":
                audio_url = f"{s['R2_URL']}/{task['r2_url']}"
                audio_data = requests.get(audio_url, timeout=60).content
                # 🚀 修正：動態判定 MIME 
                m_type = "audio/ogg" if ".opus" in r2_url else "audio/mpeg"
                
                headers = {"Authorization": f"Bearer {s['GROQ_KEY']}"}
                files = {'file': (task['r2_url'], audio_data, m_type)}
                data = {'model': 'whisper-large-v3', 'response_format': 'text', 'language': 'en'}
                
                stt_resp = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", 
                                         headers=headers, files=files, data=data, timeout=120)
                if stt_resp.status_code == 200:
                    sb.table("mission_intel").update({"stt_text": stt_resp.text, "intel_status": "Sum.-pre"}).eq("task_id", task_id).execute()
                    print(f"✅ [{worker_id}] Groq 轉譯完成。")
                else: raise Exception(f"Whisper Fail: {stt_resp.text}")
                del audio_data; gc.collect()
            else:
                # Gemini Native Stream
                sb.table("mission_intel").update({
                    "stt_text": "[GEMINI_2.5_NATIVE_STREAM]", "intel_status": "Sum.-pre"
                }).eq("task_id", task_id).execute()
                print(f"✅ [{worker_id}] Gemini 標籤掛載成功。")

        except Exception as e:
            print(f"💥 [STT Error]: {e}")
            sb.table("mission_intel").delete().eq("task_id", task_id).execute()

        time.sleep(15)
        gc.collect()

# =========================================================
# ✍️ 第二棒：STT to Summary (情報精煉官 - 防崩潰版)
# =========================================================
def run_stt_to_summary_mission():
    time.sleep(random.uniform(3.0, 8.0))
    sb = get_sb(); s = get_secrets()
    res = sb.table("mission_intel").select("*, mission_queue(*)").eq("intel_status", "Sum.-pre").limit(1).execute()

    if not res.data: return

    for intel in res.data:
        task_id = intel['task_id']
        provider = intel['ai_provider']
        try:
            summary = ""
            p_meta = sb.table("pod_scra_metadata").select("content").eq("key_name", "PROMPT_FALLBACK").single().execute()
            sys_prompt = p_meta.data['content'] if p_meta.data else "分析情報。"

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
                    summary = ai_resp.json().get('choices', [{}])[0].get('message', {}).get('content', "")

            elif provider == "GEMINI":
                audio_url = f"{s['R2_URL']}/{intel['mission_queue']['r2_url']}"
                m_type = "audio/ogg" if ".opus" in audio_url.lower() else "audio/mpeg"
                
                raw_bytes = requests.get(audio_url, timeout=120).content
                b64_audio = base64.b64encode(raw_bytes).decode('utf-8')
                del raw_bytes; gc.collect()

                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={s['GEMINI_KEY']}"
                payload = {"contents": [{"parts": [{"text": sys_prompt}, {"inline_data": {"mime_type": m_type, "data": b64_audio}}]}]}
                ai_resp = requests.post(gemini_url, json=payload, timeout=180)
                
                if ai_resp.status_code == 200:
                    # 🚀 安全取值：避免 Safety Filter 導致崩潰
                    resp_json = ai_resp.json()
                    candidates = resp_json.get('candidates', [])
                    if candidates and candidates[0].get('content'):
                        summary = candidates[0]['content']['parts'][0].get('text', "")
                del b64_audio; gc.collect()

            if summary:
                m = parse_intel_metrics(summary)
                sb.table("mission_intel").update({
                    "summary_text": summary, "intel_status": "Sum.-ready",
                    "report_date": datetime.now().strftime("%Y-%m-%d"), "total_score": m["score"]
                }).eq("task_id", task_id).execute()
                
                # Telegram 發送邏輯 (同前，略)
                report_msg = f"🎙️ {intel['mission_queue']['source_name']}\n📌 {intel['mission_queue']['episode_title']}\n\n{summary}"
                requests.post(f"https://api.telegram.org/bot{s['TG_TOKEN']}/sendMessage", 
                              json={"chat_id": s["TG_CHAT"], "text": report_msg[:4000], "parse_mode": "Markdown"})
                sb.table("mission_intel").update({"intel_status": "Sum.-sent"}).eq("task_id", task_id).execute()

        except Exception as e:
            print(f"💥 [Summary Error]: {e}")