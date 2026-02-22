# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v2.0 (全環境對位版)-測試Render
# 任務：3新+2舊任務、Opus壓縮、AI摘要、48H自動輪替、跨環境憑證讀取
# ---------------------------------------------------------

import os, requests, time, random, boto3, subprocess, json
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
from podcast_ai_agent import AIAgent 
from urllib.parse import urlparse

# ==========================================================================
# --- 🛡️ 核心憑證庫模組 (Vault Module) ---
# ==========================================================================

def get_secret(key, default=None):
    """
    🛡️ [工具] 跨環境憑證識別器：優先讀取 Render 內部 Secret File，若無則回退至環境變數。
    """
    # 一行註解：指定 Render 內部 Secret File 的掛載路徑。
    vault_path = "/etc/secrets/render_secret_vault.json"
    
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            # 一行註解：解析 JSON 憑證檔案並提取指定欄位。
            vault = json.load(f)
            val = vault.get("active_credentials", {}).get(key)
            if val: return val

    # 一行註解：若檔案不存在（如在 GitHub 執行），則改為讀取 Secrets 變數。
    return os.environ.get(key, default)



def trigger_render_webhook():
    # 一行註解：隨機延遲保護通訊通道。
    time.sleep(random.randint(10, 30))

    # 🎯 核心修正：強制解析網域，確保路徑精準鎖定 /fallback。
    raw_url = get_secret("RENDER_WEBHOOK_URL")
    parsed = urlparse(raw_url)
    url = f"{parsed.scheme}://{parsed.netloc}/fallback" # 一行註解：拋棄複雜路徑，強制回歸根網域拼接。
    
    auth_token = get_secret("CRON_SECRET")
    headers = {'X-Cron-Secret': auth_token, 'User-Agent': 'Mozilla/5.0'}
    payload = {'secret': auth_token, 'data': {'cmd': 'transport_handoff', 'origin': 'github_action'}}

    try:
        # 一行註解：發射握手訊號，Timeout 設定為 60s 給予基地充分喚醒時間。
        res = requests.post(url, json=payload, headers=headers, timeout=60)
        print(f"📡 [呼叫結果] 狀態碼：{res.status_code}")
    except Exception as e:
        print(f"⚠️ [呼叫異常]：{e}")

# ==========================================================================
# --- ⚔️ 戰術核心模組 (Tactics Module) ---
# ==========================================================================

def get_tactics(supabase: Client):
    # 從 Supabase 戰術板讀取當前執勤派令。
    res = supabase.table("pod_scra_tactics").select("*").eq("id", 1).execute()
    return res.data[0] if res.data else None


def update_active_worker(supabase: Client, next_worker: str, status_msg: str, is_hard_block: bool = False):
    # 一行註解：執行動態值星更迭，並紀錄最新的錯誤特徵。
    update_data = {
        "active_worker": next_worker,
        "duty_start_at": datetime.now(timezone.utc).isoformat(),
        "last_error_type": status_msg,
        "consecutive_soft_failures": 0 
    }
    if is_hard_block: update_data["github_status"] = "BLOCKED"
    supabase.table("pod_scra_tactics").update(update_data).eq("id", 1).execute()


def handle_failure_logic(supabase: Client, tactics: dict, error: Exception):
    #  分類處理任務失敗，403 觸發即時熔斷，其餘執行軟失敗累加。
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
            trigger_render_webhook() 

# ==========================================================================
# --- 🚀 運輸主控制流 (Main Pipeline) ---
# ==========================================================================

def run_transport_and_report():
    #  調用憑證識別器，統一獲取 Supabase 與 R2 的補給金鑰。
    sb_url = get_secret("SUPABASE_URL")
    sb_key = get_secret("SUPABASE_KEY")
    r2_id = get_secret("R2_ACCESS_KEY_ID")
    r2_secret = get_secret("R2_SECRET_ACCESS_KEY")
    r2_acc = get_secret("R2_ACCOUNT_ID")
    r2_bucket = get_secret("R2_BUCKET_NAME", "pod-scra-vault")
    
    if not all([sb_url, sb_key, r2_id, r2_secret, r2_acc]):
        print("❌ [補給中斷] 關鍵憑證獲取失敗，行動中止。")
        return
    
    supabase: Client = create_client(sb_url, sb_key)
    tactics = get_tactics(supabase)
    if not tactics: return

    # --- 戰術執行條件檢查 ---
    now = datetime.now(timezone.utc)
    duty_start = datetime.fromisoformat(tactics['duty_start_at'].replace('Z', '+00:00'))
    
    #  判定 48 小時周期是否已屆，執行計畫性交棒。
    if tactics['active_worker'] == 'GITHUB' and now > duty_start + timedelta(hours=tactics['rotation_hours']):
        print("⏰ [戰術輪替] 週期結束，交棒 Render...")
        update_active_worker(supabase, "RENDER", "ROTATION_SCHEDULE")
        trigger_render_webhook()
        return

    #  若目前非 GitHub 執勤，發送喚醒訊號後保持靜默。
    if tactics['active_worker'] != 'GITHUB':
        print(f"📡 [轉向] 目前由 {tactics['active_worker']} 執勤，確保 Render 喚醒...")
        if tactics['active_worker'] == 'RENDER': trigger_render_webhook()
        return

    #  ：初始化 AI 智囊團與 Cloudflare R2 傳輸客戶端。
    ai_agent = AIAgent()
    s3_client = boto3.client('s3', endpoint_url=f'https://{r2_acc}.r2.cloudflarestorage.com',
                             aws_access_key_id=r2_id, aws_secret_access_key=r2_secret, region_name='auto')

    #  從倉庫領取待處理任務，包含最新與歷史積壓物資。
    new_m = supabase.table("mission_queue").select("*").filter("status", "eq", "pending") \
        .or_("scrape_status.eq.success,scrape_status.eq.manual_check").order("created_at", desc=True).limit(1).execute()
    
    old_m = supabase.table("mission_queue").select("*").filter("status", "eq", "pending") \
        .or_("scrape_status.eq.success,scrape_status.eq.manual_check") \
        .not_.in_("id", [m['id'] for m in new_m.data]).order("created_at", desc=False).limit(1).execute()

    all_missions = new_m.data + old_m.data
    if not all_missions: return

    for index, mission_data in enumerate(all_missions):
        # 一 在任務序列中插入休息，防止雲端頻率過高觸發封鎖。
        if index > 0: time.sleep(random.randint(120, 300))

        source_name = mission_data.get('source_name', 'unknown')
        audio_url = mission_data.get('audio_url')
        raw_file, compressed_file = f"raw_{index}.mp3", f"proc_{index}.opus"
        r2_file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source_name}.opus"

        try:
            # 一行註解：執行戰前環境偽裝，模擬人類瀏覽行為進行熱身。
            session = requests.Session()
            session.get("https://www.google.com/", timeout=20)
            time.sleep(random.randint(30, 60))

            # 一行註解：以流式技術獲取音檔物資，並掛載全套擬態標頭。
            with session.get(audio_url, stream=True, timeout=300, headers={'User-Agent': 'Mozilla/5.0'}) as r:
                r.raise_for_status()
                with open(raw_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            
            # 一行註解：利用 FFmpeg 執行極限壓縮，轉化為 16K 單聲道 Opus 格式。
            subprocess.run(['ffmpeg', '-y', '-i', raw_file, '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k', compressed_file], 
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(compressed_file):
                # 一行註解：執行跨雲搬運，將壓縮後的情報封存至 R2 倉庫。
                s3_client.upload_file(compressed_file, r2_bucket, r2_file_name, ExtraArgs={'ContentType': 'audio/ogg'})
                
                # 一行註解：調用 AI 代理執行情報提煉，產出黃金等級摘要報告。
                analysis, q_score, duration = ai_agent.generate_gold_analysis(compressed_file)

                if analysis:
                    # 一行註解：整合情報內容，透過 Telegram 頻道向指揮官報戰。
                    report_msg = ai_agent.format_mission_report("Gold", mission_data.get('episode_title', 'Untitled'), audio_url, analysis, datetime.now().strftime("%m/%d/%y"), duration, source_name)
                    requests.post(f"https://api.telegram.org/bot{get_secret('TELEGRAM_BOT_TOKEN')}/sendMessage", 
                                   json={"chat_id": get_secret("TELEGRAM_CHAT_ID"), "text": report_msg, "parse_mode": "Markdown"})

                # 一行註解：回填資料庫任務狀態，宣告本次運輸圓滿達成。
                supabase.table("mission_queue").update({"status": "completed", "r2_url": r2_file_name, "mission_type": "scout_finished"}).eq("id", mission_data['id']).execute()
                supabase.table("pod_scra_tactics").update({"consecutive_soft_failures": 0}).eq("id", 1).execute()

        except Exception as e:
            # 一行註解：觸發故障損管邏輯，判定是否需要交棒給 Render。
            handle_failure_logic(supabase, tactics, e)
            break
        finally:
            # 一行註解：戰場清理，徹底移除本地暫存音檔以維護空間。
            for f in [raw_file, compressed_file]:
                if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    run_transport_and_report()