
# ---------------------------------------------------------
# src/pod_scra_intel_core.py v4.3 (2026 三位一體-情報加工官)
# 任務：1. 分流決策 2. STT 轉譯 3. 情報摘要 4. GEMINI 2.5
# 修正：MIME 動態適配、解決 NameError、強化變數定義
# ---------------------------------------------------------

import os, requests, json, time, random, base64, re, gc
from datetime import datetime, timezone
from src.pod_scra_intel_trans import compress_task_to_opus

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
# 🎤 第一棒：Audio to STT (接收 sb 參數版)
# =========================================================
def run_audio_to_stt_mission(sb): 
    """負責物資分流與轉譯啟動"""
    s = get_secrets(); worker_id = os.environ.get("WORKER_ID", "UNKNOWN"); mem_tier = int(os.environ.get("MEMORY_TIER", 256)) 
    sort_desc = (mem_tier >= 512)
    res = sb.table("mission_queue").select("*").eq("scrape_status", "completed").is_("skip_reason", "null").order("audio_size_mb", desc=sort_desc).limit(1).execute()

    if not res.data: return
    for task in res.data:
        task_id = task['id']; r2_url = task.get('r2_url', '').lower()
        try:
            # --- 🛠️ 階段 A：512MB 窄化壓縮 ---
            if mem_tier >= 512 and r2_url.endswith('.mp3'):
                success, new_url = compress_task_to_opus(task_id, task['r2_url'])
                if success:
                    sb.table("mission_queue").update({"r2_url": new_url, "audio_ext": ".opus"}).eq("id", task_id).execute()
                continue 

            # --- 🛠️ 階段 B：AI 轉譯分流 ---
            if mem_tier < 512 and r2_url.endswith('.mp3'): continue 
            check = sb.table("mission_intel").select("id").eq("task_id", task_id).execute()
            if check.data: continue 

            chosen_provider = random.choice(["GROQ", "GEMINI"])
            sb.table("mission_intel").insert({"task_id": task_id, "intel_status": "Sum.-proc", "ai_provider": chosen_provider}).execute()

            if chosen_provider == "GROQ":
                m_type = "audio/ogg" if ".opus" in r2_url else "audio/mpeg"
                audio_data = requests.get(f"{s['R2_URL']}/{task['r2_url']}", timeout=60).content
                stt_resp = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", 
                    headers={"Authorization": f"Bearer {s['GROQ_KEY']}"},
                    files={'file': (task['r2_url'], audio_data, m_type)},
                    data={'model': 'whisper-large-v3', 'response_format': 'text', 'language': 'en'}, timeout=120)
                if stt_resp.status_code == 200:
                    sb.table("mission_intel").update({"stt_text": stt_resp.text, "intel_status": "Sum.-pre"}).eq("task_id", task_id).execute()
                del audio_data; gc.collect()
            else:
                sb.table("mission_intel").update({"stt_text": "[GEMINI_2.5_NATIVE_STREAM]", "intel_status": "Sum.-pre"}).eq("task_id", task_id).execute()
        except Exception as e:
            print(f"💥 [加工中斷]: {e}"); sb.table("mission_intel").delete().eq("task_id", task_id).execute()
        time.sleep(15); gc.collect()

# =========================================================
# ✍️ 第二棒：STT to Summary (接收 sb 參數版)
# =========================================================
def run_stt_to_summary_mission(sb): 
    """讀取 STT 結果產出摘要"""
    time.sleep(random.uniform(3.0, 8.0)); s = get_secrets()
    res = sb.table("mission_intel").select("*, mission_queue(*)").eq("intel_status", "Sum.-pre").limit(1).execute()
    if not res.data: return
    for intel in res.data:
        task_id = intel['task_id']; provider = intel['ai_provider']
        try:
            summary = ""; p_meta = sb.table("pod_scra_metadata").select("content").eq("key_name", "PROMPT_FALLBACK").single().execute()
            sys_prompt = p_meta.data['content'] if p_meta.data else "分析情報。"

            if provider == "GROQ":
                payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": f"逐字稿：\n\n{intel['stt_text'][:50000]}"}], "temperature": 0.3}
                ai_resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {s['GROQ_KEY']}"}, json=payload, timeout=90)
                if ai_resp.status_code == 200: summary = ai_resp.json().get('choices', [{}])[0].get('message', {}).get('content', "")

            elif provider == "GEMINI":
                a_url = f"{s['R2_URL']}/{intel['mission_queue']['r2_url']}"; m_type = "audio/ogg" if ".opus" in a_url.lower() or ".ogg" in a_url.lower() else "audio/mpeg"
                raw_bytes = requests.get(a_url, timeout=120).content
                b64_audio = base64.b64encode(raw_bytes).decode('utf-8'); del raw_bytes; gc.collect()
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={s['GEMINI_KEY']}"
                payload = {"contents": [{"parts": [{"text": sys_prompt}, {"inline_data": {"mime_type": m_type, "data": b64_audio}}]}]}
                ai_resp = requests.post(g_url, json=payload, timeout=180)
                if ai_resp.status_code == 200:
                    cands = ai_resp.json().get('candidates', [])
                    if cands and cands[0].get('content'): summary = cands[0]['content']['parts'][0].get('text', "")
                del b64_audio; gc.collect()

            if summary:
                m = parse_intel_metrics(summary); sb.table("mission_intel").update({"summary_text": summary, "intel_status": "Sum.-ready", "report_date": datetime.now().strftime("%Y-%m-%d"), "total_score": m["score"]}).eq("task_id", task_id).execute()
                report_msg = f"🎙️ {intel['mission_queue']['source_name']}\n📌 {intel['mission_queue']['episode_title']}\n\n{summary}"
                requests.post(f"https://api.telegram.org/bot{s['TG_TOKEN']}/sendMessage", json={"chat_id": s["TG_CHAT"], "text": report_msg[:4000], "parse_mode": "Markdown"})
                sb.table("mission_intel").update({"intel_status": "Sum.-sent"}).eq("task_id", task_id).execute()
                print(f"🎉 [{provider}] 情報傳遞成功。")
        except Exception as e: print(f"💥 [摘要階段異常]: {e}")