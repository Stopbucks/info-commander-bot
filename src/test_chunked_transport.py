# ---------------------------------------------------------
# 本程式碼：src/test_chunked_transport.py v3.0 (全鏈路演習版)
# 任務：60MB 門檻、4MB 動態分段、擬態搬運、FFmpeg 壓縮、AI 摘要、Telegram 報戰
# ---------------------------------------------------------
import os, requests, time, random, boto3, math, subprocess
from supabase import create_client, Client
from datetime import datetime, timezone
from podcast_ai_agent import AIAgent 

# --- [區塊一：物資規格偵察 (HEAD Recon)] ---
def get_target_specs(url):
    """一行註解：預查檔案大小，作為 60MB 門檻與分段決策依據。"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebkit/537.36'}
    try:
        r = requests.head(url, headers=headers, timeout=15, allow_redirects=True)
        return int(r.headers.get('Content-Length', 0))
    except Exception as e:
        print(f"⚠️ [預查失敗] 無法獲取大小：{e}")
        return 0

# --- [區塊二：物流中繼模組 (Relay)] ---
def fetch_chunk_via_proxy(target_url, start, end, api_key):
    """一行註解：透過 WebScraping.ai 透傳 Range 標頭進行 4MB 級別抓取。"""
    proxy_params = {
        'api_key': api_key, 'url': target_url, 'keep_headers': 'true', 'proxy': 'residential'
    }
    custom_headers = {
        'Range': f'bytes={start}-{end}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebkit/537.36'
    }
    try:
        resp = requests.get('https://api.webscraping.ai/html', params=proxy_params, headers=custom_headers, timeout=60)
        return resp.content if resp.status_code in [200, 206] else None
    except Exception: return None

# --- [區塊三：縫合與重編模組 (Assembler)] ---
def assemble_and_compress(task_id, chunk_count, final_name):
    """一行註解：二進位縫合片段，並發動 16K/Mono/Opus 壓縮戰術。"""
    temp_raw = f"{task_id}_raw.mp3"
    with open(temp_raw, 'wb') as outfile:
        for i in range(chunk_count):
            part_path = f"parts/part_{i}.bin"
            if os.path.exists(part_path):
                with open(part_path, 'rb') as infile: outfile.write(infile.read())
                os.remove(part_path)

    print(f"🗜️ [壓縮中] 執行 FFmpeg 高效轉碼 (16K/Mono/Opus)...")
    subprocess.run([
        'ffmpeg', '-y', '-i', temp_raw,
        '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k',
        final_name
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(temp_raw): os.remove(temp_raw)
    return os.path.getsize(final_name)

# --- [主演習程序 (Main Expedition)] ---
def run_full_cycle_test():
    # 1. 補給初始化
    scra_key = os.environ.get("WEBSCRAP_API_KEY")
    sb_url, sb_key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    r2_id, r2_secret = os.environ.get("R2_ACCESS_KEY_ID"), os.environ.get("R2_SECRET_ACCESS_KEY")
    r2_acc, r2_bucket = os.environ.get("R2_ACCOUNT_ID"), os.environ.get("R2_BUCKET_NAME")
    
    supabase: Client = create_client(sb_url, sb_key)
    ai_agent = AIAgent()
    s3_client = boto3.client('s3', endpoint_url=f'https://{r2_acc}.r2.cloudflarestorage.com',
                             aws_access_key_id=r2_id, aws_secret_access_key=r2_secret)

    # 🚀 2. 領取 1 筆待命物資
    res = supabase.table("mission_queue").select("*").eq("status", "pending").eq("scrape_status", "success").limit(1).execute()
    if not res.data: 
        print("☕ [待命] 暫無物資需演習。")
        return
    
    m = res.data[0]
    target_url = m['audio_url']
    source_name = m.get('source_name', 'TEST')
    
    # 🚀 3. 戰略評估 (60MB 門檻)
    total_size = get_target_specs(target_url)
    total_mb = total_size / (1024 * 1024)
    
    if total_size == 0 or total_mb > 60:
        print(f"🛑 [撤退] 物資體積 ({total_mb:.2f}MB) 超標或無回應，不予搬運。")
        return

    # 一行註解：動態計算分段，確保總請求 <= 20 次，單次約 3-4MB。
    chunk_size = max(3.5 * 1024 * 1024, math.ceil(total_size / 20))
    num_chunks = math.ceil(total_size / chunk_size)
    if not os.path.exists('parts'): os.makedirs('parts')

    print(f"🚀 [演習開始] {source_name} | 總重：{total_mb:.2f}MB | 分段：{num_chunks}")

    # 🚀 4. 序列化擬態搬運
    for i in range(num_chunks):
        if i > 0:
            # 一行註解：針對 3.5MB 以上的大片段，給予更長的伺服器「喘息時間」。
            jitter = random.uniform(8.5, 16.2) 
            print(f"🕒 [擬態緩衝] 正在進行大片段冷卻，等待 {jitter:.2f} 秒...")
            time.sleep(jitter)

        start = i * chunk_size
        end = min(start + chunk_size - 1, total_size - 1)


        chunk_data = fetch_chunk_via_proxy(target_url, start, end, scra_key)
        
        if chunk_data:
            with open(f"parts/part_{i}.bin", "wb") as f: f.write(chunk_data)
            print(f"✅ 片段 {i} 成功。")
        else:
            print(f"❌ [斷供] 片段 {i} 遺失，不補件直接撤退。")
            return

    # 🚀 5. 縫合、壓縮與 AI 分析
    final_opus = f"RELAY_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source_name}.opus"
    compressed_size = assemble_and_compress(m['id'], num_chunks, final_opus)
    
    print(f"🧠 [AI 行動] 呼叫智囊團執行摘要...")
    analysis, q_score, duration = ai_agent.generate_gold_analysis(final_opus)

    if analysis:
        # 🚀 6. Telegram 報戰
        print(f"📡 [情報推送] 正在發布演習結果...")
        report_msg = ai_agent.format_mission_report(
            "Relay-Test", m['episode_title'], target_url, analysis, 
            datetime.now().strftime("%m/%d/%y"), duration, source_name
        )
        report_msg += f"\n\n📊 [物流數據]\n原始：{total_mb:.2f}MB\n分段：{num_chunks}\n壓縮後：{compressed_size/(1024*1024):.2f}MB"
        
        requests.post(f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage", 
                      json={"chat_id": os.environ.get("TELEGRAM_CHAT_ID"), "text": report_msg, "parse_mode": "Markdown"})

    # 🚀 7. 入庫與歸檔
    s3_client.upload_file(final_opus, r2_bucket, final_opus, ExtraArgs={'ContentType': 'audio/ogg'})
    supabase.table("mission_queue").update({
        "status": "completed", "r2_url": final_opus, "mission_type": "relay_finished"
    }).eq("id", m['id']).execute()
    
    print(f"🏆 [演習達成] 物資已入庫且任務已結案。")
    if os.path.exists(final_opus): os.remove(final_opus)

if __name__ == "__main__":
    run_full_cycle_test()