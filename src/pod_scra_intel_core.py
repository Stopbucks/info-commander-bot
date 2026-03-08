
# ---------------------------------------------------------
# src/pod_scra_intel_core.py v4.3 (2026 三位一體-情報加工官)
# 任務：1. 階梯式任務發動 2. 記憶體強制回收 3. API 重試邏輯 4. GEMINI 2.5
# 修正：MIME 動態適配、解決 NameError、強化變數定義
# ---------------------------------------------------------
import os, requests, json, time, random, base64, re, gc
from datetime import datetime, timezone
from supabase import create_client

# 🚀 導入物流官提供的壓縮引擎 (跨檔案連動關鍵)
from src.pod_scra_intel_trans import compress_task_to_opus

def get_secrets():
    """集中管理所有外部 API 與 R2 金鑰"""
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
    """建立並回傳 Supabase 連線物件 (解決 NameError)"""
    s = get_secrets()
    return create_client(s["SB_URL"], s["SB_KEY"])

def parse_intel_metrics(text):
    """從 AI 文本中精確提取評分與實證數指標"""
    metrics = {"score": 0, "stated": 0, "inferred": 0, "subjective": 0, "evidence": 0}
    try:
        s_match = re.search(r"綜合情報分.*?(\d+)", text)
        if s_match: metrics["score"] = int(s_match.group(1))
        e_match = re.search(r"關鍵實證數：(\d+)", text)
        if e_match: metrics["evidence"] = int(e_match.group(1))
    except: pass
    return metrics
# =========================================================
# 🎤 第一棒：Audio to STT (決策中樞 - 鋼鐵加固版)
# =========================================================
def run_audio_to_stt_mission():
    """負責物資分流：512MB 改裝 MP3，256MB 只處理轉譯任務"""
    sb = get_sb(); s = get_secrets()
    worker_id = os.environ.get("WORKER_ID", "UNKNOWN")
    mem_tier = int(os.environ.get("MEMORY_TIER", 256)) 
    
    # 🚀 排序分流：512MB 咬大貨(DESC)，256MB 撿小貨(ASC)
    sort_desc = (mem_tier >= 512)
    res = sb.table("mission_queue").select("*")\
            .eq("scrape_status", "completed").is_("skip_reason", "null")\
            .order("audio_size_mb", desc=sort_desc).limit(2 if sort_desc else 1).execute()

    if not res.data: return

    for task in res.data:
        # 🚀 防崩潰加固：進入 loop 立即賦值核心變數，確保 Exception 捕獲正確 ID
        task_id = task['id']
        r2_url = task.get('r2_url', '').lower()

        try:
            # --- 🛠️ 戰術分鏡 A：512MB 改裝任務 ---
            if mem_tier >= 512 and r2_url.endswith('.mp3'):
                print(f"📡 [{worker_id}] 偵測到 MP3 重物，下令物流官啟動窄化壓縮...")
                success, new_url = compress_task_to_opus(task_id, task['r2_url'])
                if success:
                    sb.table("mission_queue").update({
                        "r2_url": new_url, "audio_ext": ".opus", "used_provider": f"{worker_id}_L-OPT"
                    }).eq("id", task_id).execute()
                    print(f"✅ [{worker_id}] 改裝廠回填完成：{new_url}")
                continue # 完成改裝後退出本輪，待下一輪領取小包

            # --- 🛠️ 戰術分鏡 B：AI 轉譯任務 ---
            if mem_tier < 512 and r2_url.endswith('.mp3'): continue # 🚀 256MB 自動規避 MP3

            check = sb.table("mission_intel").select("id").eq("task_id", task_id).execute()
            if check.data: continue # 🚀 若已在加工中則跳過

            # 🚀 關鍵修正：在 Insert 前先決定 Provider，防止 NameError
            chosen_provider = random.choice(["GROQ", "GEMINI"])
            sb.table("mission_intel").insert({
                "task_id": task_id, "intel_status": "Sum.-proc", "ai_provider": chosen_provider
            }).execute()

            if chosen_provider == "GROQ":
                # 🚀 MIME 動態適配：Opus 需對應 audio/ogg
                m_type = "audio/ogg" if ".opus" in r2_url else "audio/mpeg"
                audio_data = requests.get(f"{s['R2_URL']}/{task['r2_url']}", timeout=60).content
                stt_resp = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", 
                    headers={"Authorization": f"Bearer {s['GROQ_KEY']}"},
                    files={'file': (task['r2_url'], audio_data, m_type)},
                    data={'model': 'whisper-large-v3', 'response_format': 'text', 'language': 'en'}, timeout=120)
                if stt_resp.status_code == 200:
                    sb.table("mission_intel").update({"stt_text": stt_resp.text, "intel_status": "Sum.-pre"}).eq("task_id", task_id).execute()
                else: raise Exception(f"Whisper Fail: {stt_resp.text}")
                del audio_data; gc.collect()
            else:
                # 🚀 Gemini Native Stream 標記 (由第二棒完成加工)
                sb.table("mission_intel").update({
                    "stt_text": "[GEMINI_2.5_NATIVE_STREAM]", "intel_status": "Sum.-pre"
                }).eq("task_id", task_id).execute()
                print(f"✅ [{worker_id}] Gemini 標籤掛載成功")

        except Exception as e:
            print(f"💥 [STT 加工異常]: {e}")
            sb.table("mission_intel").delete().eq("task_id", task_id).execute()

        time.sleep(15) # 任務間冷卻
        gc.collect() # 回收內存
# =========================================================
# ✍️ 第二棒：STT to Summary (情報精煉官 - 加固版)
# =========================================================
def run_stt_to_summary_mission():
    """解析轉譯結果並產出最終情報摘要"""
    time.sleep(random.uniform(3.0, 8.0))
    sb = get_sb(); s = get_secrets()
    res = sb.table("mission_intel").select("*, mission_queue(*)").eq("intel_status", "Sum.-pre").limit(1).execute()

    if not res.data: return

    for intel in res.data:
        task_id = intel['task_id']
        provider = intel['ai_provider']
        try:
            summary = ""; p_meta = sb.table("pod_scra_metadata").select("content").eq("key_name", "PROMPT_FALLBACK").single().execute()
            sys_prompt = p_meta.data['content'] if p_meta.data else "請分析情報。"

            if provider == "GROQ":
                # 🚀 Groq 情報提煉邏輯
                payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": f"逐字稿：\n\n{intel['stt_text'][:50000]}"}], "temperature": 0.3}
                ai_resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {s['GROQ_KEY']}"}, json=payload, timeout=90)
                if ai_resp.status_code == 200: summary = ai_resp.json().get('choices', [{}])[0].get('message', {}).get('content', "")

            elif provider == "GEMINI":
                # 🚀 Gemini 原生流加工邏輯 (具備 MIME 自動適配)
                a_url = f"{s['R2_URL']}/{intel['mission_queue']['r2_url']}"
                m_type = "audio/ogg" if ".opus" in a_url.lower() or ".ogg" in a_url.lower() else "audio/mpeg"
                raw_bytes = requests.get(a_url, timeout=120).content
                b64_audio = base64.b64encode(raw_bytes).decode('utf-8')
                del raw_bytes; gc.collect()
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={s['GEMINI_KEY']}"
                payload = {"contents": [{"parts": [{"text": sys_prompt}, {"inline_data": {"mime_type": m_type, "data": b64_audio}}]}]}
                ai_resp = requests.post(g_url, json=payload, timeout=180)
                if ai_resp.status_code == 200:
                    # 🚀 安全解析：避免 Safety Filter 導致回應為空時崩潰
                    cands = ai_resp.json().get('candidates', [])
                    if cands and cands[0].get('content'): summary = cands[0]['content']['parts'][0].get('text', "")
                del b64_audio; gc.collect()

            if summary:
                # --- 2. 成果入庫與通報 ---
                m = parse_intel_metrics(summary)
                sb.table("mission_intel").update({"summary_text": summary, "intel_status": "Sum.-ready", "report_date": datetime.now().strftime("%Y-%m-%d"), "total_score": m["score"]}).eq("task_id", task_id).execute()
                report_msg = f"🎙️ {intel['mission_queue']['source_name']}\n📌 {intel['mission_queue']['episode_title']}\n\n{summary}"
                requests.post(f"https://api.telegram.org/bot{s['TG_TOKEN']}/sendMessage", json={"chat_id": s["TG_CHAT"], "text": report_msg[:4000], "parse_mode": "Markdown"})
                sb.table("mission_intel").update({"intel_status": "Sum.-sent"}).eq("task_id", task_id).execute()
                print(f"🎉 [{provider}] 情報傳遞成功。")

        except Exception as e:
            print(f"💥 [摘要階段異常]: {e}")