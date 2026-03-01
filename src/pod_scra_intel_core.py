# ---------------------------------------------------------
# src/pod_scra_intel_core.py v1.4 (2026 二代大腦升級版)
# 任務：1. 隨機分流 2. Opus 協議 3. 升級 Gemini 2.5 Flash 原生處理
# ---------------------------------------------------------
import os, requests, json, time, random, base64
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

# =========================================================
# 🎤 第一棒：Audio to STT (音訊轉譯官 / 產線骰子手)
# =========================================================
def run_audio_to_stt_mission():
    sb = get_sb(); s = get_secrets()
    
    # 領取已下載至 R2 但尚未開始 AI 處理的任務
    query = sb.table("mission_queue").select("id, r2_url, episode_title")\
              .eq("scrape_status", "completed").limit(1).execute()
    
    for task in (query.data or []):
        task_id = task['id']
        check = sb.table("mission_intel").select("id").eq("task_id", task_id).execute()
        if check.data: continue

        # 🎲 擲骰子：50% GROQ (走 STT 路線), 50% GEMINI (走原生音訊路線)
        chosen_provider = random.choice(["GROQ", "GEMINI"])
        print(f"🎲 [分流決策] 任務 {task_id[:8]} -> 指派給 [{chosen_provider}]")
        
        # 標記施工中 (Sum.-proc) 並鎖定產線標籤
        sb.table("mission_intel").insert({
            "task_id": task_id, 
            "intel_status": "Sum.-proc", 
            "ai_provider": chosen_provider
        }).execute()

        try:
            # --- [產線 A：GROQ 轉譯路徑] ---
            if chosen_provider == "GROQ":
                audio_url = f"{s['R2_URL']}/{task['r2_url']}"
                audio_resp = requests.get(audio_url)
                
                headers = {"Authorization": f"Bearer {s['GROQ_KEY']}"}
                files = {'file': (task['r2_url'], audio_resp.content, 'audio/ogg')}
                data = {'model': 'whisper-large-v3', 'response_format': 'text', 'language': 'en'}
                
                stt_resp = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", 
                                         headers=headers, files=files, data=data)
                
                if stt_resp.status_code == 200:
                    sb.table("mission_intel").update({
                        "stt_text": stt_resp.text, 
                        "intel_status": "Sum.-pre"
                    }).eq("task_id", task_id).execute()
                    print(f"✅ [第一棒：GROQ] 逐字稿轉譯完成。")
                else:
                    raise Exception(f"GROQ API Error: {stt_resp.status_code}")

            # --- [產線 B：GEMINI 2.5 原生路徑] ---
            else:
                # Gemini 2.5 具備頂級聽力，直接交棒給第二棒執行音訊摘要
                sb.table("mission_intel").update({
                    "stt_text": "[GEMINI_2.5_NATIVE_FLOW]", 
                    "intel_status": "Sum.-pre"
                }).eq("task_id", task_id).execute()
                print(f"✅ [第一棒：GEMINI 2.5] 已鎖定原生音訊流。")

        except Exception as e:
            print(f"❌ [第一棒異常]: {e}")
            sb.table("mission_intel").delete().eq("task_id", task_id).execute()

# =========================================================
# ✍️ 第二棒：STT to Summary (情報精煉官)
# =========================================================
def run_stt_to_summary_mission():
    sb = get_sb(); s = get_secrets()
    
    # 領取待摘要 (Sum.-pre) 的任務
    query = sb.table("mission_intel").select("*, mission_queue(episode_title, source_name, r2_url)")\
              .eq("intel_status", "Sum.-pre").limit(1).execute()
    
    for intel in (query.data or []):
        task_id = intel['task_id']
        provider = intel['ai_provider']
        print(f"✍️ [第二棒啟動] 產線: {provider} | 任務: {intel['mission_queue']['episode_title'][:20]}")
        
        # 領取提示詞燃料
        p_res = sb.table("pod_scra_metadata").select("content").eq("key_name", "PROMPT_FALLBACK").single().execute()
        sys_prompt = p_res.data['content'] if p_res.data else "請摘要情報。"

        try:
            summary = ""
            
            # --- [GROQ 產線摘要] ---
            if provider == "GROQ":
                stt_content = intel['stt_text']
                headers = {"Authorization": f"Bearer {s['GROQ_KEY']}", "Content-Type": "application/json"}
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": f"分析逐字稿：\n\n{stt_content[:50000]}"}
                    ]
                }
                ai_resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                if ai_resp.status_code == 200:
                    summary = ai_resp.json()['choices'][0]['message']['content']

            # --- [GEMINI 2.5 原生音訊摘要] ---
            elif provider == "GEMINI":
                audio_url = f"{s['R2_URL']}/{intel['mission_queue']['r2_url']}"
                audio_data = base64.b64encode(requests.get(audio_url).content).decode('utf-8')
                
                # 🚀 升級為二代大腦 2.5 Flash API 端點
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={s['GEMINI_KEY']}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": sys_prompt},
                            {"inline_data": {"mime_type": "audio/ogg", "data": audio_data}}
                        ]
                    }]
                }
                ai_resp = requests.post(gemini_url, headers=headers, json=payload)
                if ai_resp.status_code == 200:
                    summary = ai_resp.json()['candidates'][0]['content']['parts'][0]['text']

            # --- [結算推送] ---
            if summary:
                sb.table("mission_intel").update({"summary_text": summary, "intel_status": "Sum.-ready"}).eq("task_id", task_id).execute()
                
                report_msg = f"🎙️ {intel['mission_queue']['source_name']}\n📌 {intel['mission_queue']['episode_title']}\n\n{summary}"
                requests.post(f"https://api.telegram.org/bot{s['TG_TOKEN']}/sendMessage", 
                             json={"chat_id": s["TG_CHAT"], "text": report_msg[:4000]})
                
                sb.table("mission_intel").update({"intel_status": "Sum.-sent"}).eq("task_id", task_id).execute()
                print(f"✅ [第二棒：{provider}] 情報已發送。")
                
        except Exception as e:
            print(f"❌ [第二棒異常]: {e}")