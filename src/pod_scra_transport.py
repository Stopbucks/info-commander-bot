
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v1.0 (戰術輪替模組化版)
# 任務：3新+2舊任務、Opus壓縮、AI摘要、48H自動輪替調度
# ---------------------------------------------------------

import os, requests, time, random, boto3, subprocess
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
from podcast_ai_agent import AIAgent 

# --- 區塊一：戰術核心模組 (Tactics Core) ---
def get_tactics(supabase: Client):
    # 一行註解：從戰術板讀取唯一的執勤派令。
    res = supabase.table("pod_scra_tactics").select("*").eq("id", 1).execute()
    return res.data[0] if res.data else None


def update_active_worker(supabase: Client, next_worker: str, status_msg: str, is_hard_block: bool = False):
    # 一行註解：更新資料庫狀態，切換值星官並紀錄錯誤。
    update_data = {
        "active_worker": next_worker,
        "duty_start_at": datetime.now(timezone.utc).isoformat(),
        "last_error_type": status_msg,
        "consecutive_soft_failures": 0 # 換班時重置軟失敗計數
    }
    if is_hard_block: update_data["github_status"] = "BLOCKED"
    supabase.table("pod_scra_tactics").update(update_data).eq("id", 1).execute()


def handle_failure_logic(supabase: Client, tactics: dict, error: Exception):
    # 一行註解：分級處理失敗，403立即換班，其餘累加失敗次數。
    err_str = str(error)
    if "403" in err_str:
        print(f"🚨 [硬斷路] 偵測到 403 封鎖，立即移交 Render 據點...")
        update_active_worker(supabase, "RENDER", "403_BLOCK", is_hard_block=True)
        trigger_render_webhook()
    else:
        new_soft_count = tactics.get('consecutive_soft_failures', 0) + 1
        print(f"⚠️ [軟失敗] 次數：{new_soft_count}/{tactics['soft_failure_threshold']}")
        supabase.table("pod_scra_tactics").update({"consecutive_soft_failures": new_soft_count}).eq("id", 1).execute()
        if new_soft_count >= tactics['soft_failure_threshold']:
            print("🛑 [閾值觸發] 連續軟失敗過多，強制換班...")
            update_active_worker(supabase, "RENDER", "SOFT_FAILURE_LIMIT")
            trigger_render_webhook() # 一行註解：在軟失敗達標強制換班後，亦同步喚醒 Render 據點。


def trigger_render_webhook():
    # 呼叫遠端據點前進行隨機等待，避免多個程序同時競爭 Render 資源。
    wait_time = random.randint(10, 30)
    print(f"⏳ [通訊防護] 避開競爭呼叫，隨機等待 {wait_time} 秒後發送訊號...")
    time.sleep(wait_time)
    # 一行註解：發送 Webhook 喚醒 Render 據點接手任務。
    url = os.environ.get("RENDER_WEBHOOK_URL") + "/fallback"
    #requests.post(url, headers={'X-Cron-Secret': os.environ.get("CRON_SECRET")}, timeout=10)

    try:
        # 一行註解：發送帶有超時保護的 Webhook，確保不會因為 Render 反應慢而卡死。
        res = requests.post(
            url, 
            headers={'X-Cron-Secret': os.environ.get("CRON_SECRET")}, 
            timeout=15
        )
        print(f"📡 [呼叫結果] 狀態碼：{res.status_code}")
    except Exception as e:
        print(f"⚠️ [呼叫異常] 無法聯繫 Render 據點：{e}")

# --- 區塊二：主邏輯控制流 (Main Flow) ---
def run_transport_and_report():
    # 1. 補給金鑰初始化
    sb_url, sb_key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    r2_id, r2_secret = os.environ.get("R2_ACCESS_KEY_ID"), os.environ.get("R2_SECRET_ACCESS_KEY")
    r2_acc, r2_bucket = os.environ.get("R2_ACCOUNT_ID"), os.environ.get("R2_BUCKET_NAME", "pod-scra-vault")
    
    if not all([sb_url, sb_key, r2_id, r2_secret, r2_acc]): return
    
    supabase: Client = create_client(sb_url, sb_key)
    tactics = get_tactics(supabase)
    if not tactics: return

    # --- 定位線：戰術檢查區塊 ---
    now = datetime.now(timezone.utc)
    duty_start = datetime.fromisoformat(tactics['duty_start_at'].replace('Z', '+00:00'))
    
    # 🚀 檢查 A：是否已到 48H 輪替時間？
    if tactics['active_worker'] == 'GITHUB' and now > duty_start + timedelta(hours=tactics['rotation_hours']):
        print("⏰ [戰術輪替] 48小時執勤結束，交棒 Render...")
        update_active_worker(supabase, "RENDER", "ROTATION_SCHEDULE")
        trigger_render_webhook()
        return

    # 🚀 檢查 B：目前是否由 GitHub 執勤？
    if tactics['active_worker'] != 'GITHUB':
        print(f"📡 [轉向] 目前由 {tactics['active_worker']} 執勤，發送喚醒信號並待命。")
        if tactics['active_worker'] == 'RENDER': trigger_render_webhook()
        return

    # 2. 初始化傳輸組件
    ai_agent = AIAgent()
    s3_client = boto3.client('s3', endpoint_url=f'https://{r2_acc}.r2.cloudflarestorage.com',
                             aws_access_key_id=r2_id, aws_secret_access_key=r2_secret, region_name='auto')


    # --- 區塊：3新 + 2舊 混編領取邏輯 (不變，維持優良戰術) ---#02/20測試期間改2新1舊
    # ----#02/21 測試期間改1新1舊
    # -------------------------------------------------------------------------
    new_m = supabase.table("mission_queue").select("*") \
        .filter("status", "eq", "pending") \
        .or_("scrape_status.eq.success,scrape_status.eq.manual_check") \
        .order("created_at", desc=True).limit(2).execute()
    
    picked_ids = [m['id'] for m in new_m.data]
    old_m = supabase.table("mission_queue").select("*") \
        .filter("status", "eq", "pending") \
        .or_("scrape_status.eq.success,scrape_status.eq.manual_check") \
        .not_.in_("id", picked_ids) \
        .order("created_at", desc=False).limit(1).execute()

    all_missions = new_m.data + old_m.data
    
    if not all_missions:
        print("☕ [待命] 倉庫暫無待搬運物資。")
        return

    print(f"📦 [裝載] 混合領取完成：新物資 {len(new_m.data)} 筆，舊物資 {len(old_m.data)} 筆。")

    
    # 🚀 啟動多任務處理流水線
    for index, mission_data in enumerate(all_missions):
        # A. 任務間大抖動 (保持穩定性)
        if index > 0:
            task_gap = random.randint(120, 300)
            print(f"⏳ [休息] 為避開頻率限制，等待 {task_gap//60} 分鐘...")
            time.sleep(task_gap)

        source_name = mission_data.get('source_name', 'unknown')
        audio_url = mission_data.get('audio_url')
        episode_title = mission_data.get('episode_title', 'Untitled')
        provider_info = mission_data.get('used_provider', 'Legacy/RSS')
        
        if not audio_url:
            print(f"⚠️ 任務 {mission_data['id']} 無音訊網址，跳過。")
            continue

        raw_file = f"raw_{index}.mp3"
        compressed_file = f"proc_{index}.opus"
        r2_file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source_name}.opus"

        try:
            #--- 定位線 以下修改下載與預熱區塊 ---#
            # 🚀 1. 預熱瀏覽：隨機選取高權重網站
            warmup_target = random.choice(["https://www.apple.com/apple-podcasts/", "https://www.google.com/"])
            print(f"📡 [預熱] 正在進行前置瀏覽：{warmup_target}")
            session = requests.Session()
            session.get(warmup_target, timeout=20)
            
            # 🚀 2. 深度 Jitter (5-10 分鐘)
            deep_jitter = random.randint(300, 600)
            print(f"🕒 [擬態休眠] 深度偽裝中，等待 {deep_jitter//60} 分鐘...")
            time.sleep(deep_jitter)

            # 🚀 3. 流式下載處理 (全套擬態標頭)
            print(f"📥 [下載中] 正在獲取物資：{source_name}...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Referer': 'https://podbay.fm/',
                'Accept': 'audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            # 一行註解：確保使用 session 與全套 headers 進行偽裝下載。
            with session.get(audio_url, stream=True, timeout=300, headers=headers) as r:
                r.raise_for_status()
                with open(raw_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            
            # --- 核心：FFmpeg 壓縮技術 (16K/Mono/Opus) ---
            print(f"🗜️ [壓縮中] 執行高效率轉碼...")
            # 一行註解：將音檔轉為 16kHz 單聲道 Opus 格式。
            subprocess.run([
                'ffmpeg', '-y', '-i', raw_file,
                '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k',
                compressed_file
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # ... 接下來是推向 R2 與 AI 分析的邏輯  ...

            if os.path.exists(compressed_file):
                # 4. 推向 R2
                print(f"🚀 [運輸中] 將轉碼情報推向 R2：{r2_file_name}")
                # 🚀 修正：ContentType 改為音訊通用格式，Bucket 改為變數控制
                s3_client.upload_file(compressed_file, r2_bucket, r2_file_name, ExtraArgs={'ContentType': 'audio/ogg'})
                
                # 5. AI 分析
                print(f"🧠 [AI 行動] 呼叫智囊團執行摘要...")
                analysis, q_score, duration = ai_agent.generate_gold_analysis(compressed_file)

                if analysis:
                    # 6. Telegram 報戰
                    print(f"📡 [情報發布] 正在推送報戰...")
                    date_label = datetime.now().strftime("%m/%d/%y")
                    report_msg = ai_agent.format_mission_report(
                        "Gold", episode_title, audio_url, analysis, date_label, duration, source_name
                    )
                    
                    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
                    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
                    requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage", 
                                   json={"chat_id": tg_chat_id, "text": report_msg, "parse_mode": "Markdown"})

                # 7. 更新資料庫
                supabase.table("mission_queue").update({
                    "status": "completed",
                    "r2_url": r2_file_name,
                    "mission_type": "scout_finished_with_ai_compressed"
                }).eq("id", mission_data['id']).execute()
                print(f"🏆 [任務達成] {episode_title[:15]}... 搬運歸檔完成。")
                supabase.table("pod_scra_tactics").update({"consecutive_soft_failures": 0}).eq("id", 1).execute()

        except Exception as e:
            # 一行註解：交由戰術失敗模組判定處理方式。
            handle_failure_logic(supabase, tactics, e)
            break # 發生異常時停止本次 GitHub 流程
        
        finally:
            # 清理所有本地暫存
            for f in [raw_file, compressed_file]:
                if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    run_transport_and_report()