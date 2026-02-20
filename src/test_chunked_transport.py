# ---------------------------------------------------------
# 本程式碼：src/test_chunked_transport.py v3.4 (直連解析強化版)
# 任務：60MB 門檻、5.5MB 動態分段、先行解析直連、FFmpeg 容錯轉碼、AI 報戰
# ---------------------------------------------------------
import os, requests, time, random, boto3, math, subprocess
from supabase import create_client, Client
from datetime import datetime, timezone
from podcast_ai_agent import AIAgent 

# --- [區塊一：物資規格與直連偵察 (HEAD Recon)] ---
def get_target_specs(url):
    """一行註解：預查檔案大小並追蹤最終重新導向網址，確保分段下載標頭不遺失。"""
    stealth_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        # 🚀 關鍵：allow_redirects=True 獲取經過多次轉址後的最終實體檔案位址
        r = requests.head(url, headers=stealth_headers, timeout=15, allow_redirects=True)
        total_size = int(r.headers.get('Content-Length', 0))
        resolved_url = r.url
        print(f"📡 [導航解析] 最終直連位址：{resolved_url[:60]}...")
        return total_size, resolved_url
    except Exception as e:
        print(f"⚠️ [預查失敗] 無法獲取大小或解析位址：{e}")
        return 0, url

# --- [區塊二：強化版物流中繼模組] ---
def fetch_chunk_via_proxy(target_url, start, end, api_key):
    """一行註解：透過 WebScraping.ai 住宅代理抓取二進位碎片，並執行 HTML 污染檢核。"""
    proxy_params = {
        'api_key': api_key, 'url': target_url, 
        'keep_headers': 'true', 'proxy': 'residential', 'timeout': 30000
    }
    custom_headers = {
        'Range': f'bytes={start}-{end}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebkit/537.36'
    }
    try:
        resp = requests.get('https://api.webscraping.ai/html', params=proxy_params, headers=custom_headers, timeout=60)
        if resp.status_code in [200, 206]:
            if b"<html" in resp.content[:100].lower():
                print(f"⚠️ [攔截警報] 代理回傳 HTML 而非音訊，座標：{start}-{end}")
                return None
            return resp.content
        return None
    except Exception: return None

# --- [區塊三：強化版縫合與壓縮] ---
def assemble_and_compress(task_id, chunk_count, final_name, source_url):
    """一行註解：根據直連網址動態決定副檔名，並執行具備 Faststart 特性的 Opus 壓縮。"""
    ext = ".mp3"
    if ".m4a" in source_url.lower(): ext = ".m4a"
    elif ".wav" in source_url.lower(): ext = ".wav"
    
    temp_raw = f"{task_id}_raw{ext}"
    with open(temp_raw, 'wb') as outfile:
        for i in range(chunk_count):
            part_path = f"parts/part_{i}.bin"
            if os.path.exists(part_path):
                with open(part_path, 'rb') as infile: outfile.write(infile.read())
                os.remove(part_path)

    print(f"🗜️ [壓縮中] 原始格式 {ext}，執行 16K/Mono/Opus 轉碼...")
    # 一行註解：加入 ignore_err 與 faststart，確保串流播放完整性。
    result = subprocess.run([
        'ffmpeg', '-y', '-err_detect', 'ignore_err',
        '-i', temp_raw,
        '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k',
        '-movflags', 'faststart', final_name
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ [FFmpeg 報錯] {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, result.args)
    
    if os.path.exists(temp_raw): os.remove(temp_raw)
    return os.path.getsize(final_name)

# --- [主演習程序] ---
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

    # 🚀 2. 領取 1 筆待命物資 (廣域雷達版)
    res = supabase.table("mission_queue").select("*") \
        .eq("status", "pending") \
        .not_.is_("audio_url", "null") \
        .or_("scrape_status.eq.success,scrape_status.eq.pending") \
        .order("created_at", desc=True).limit(1).execute()

    if not res.data: 
        print("☕ [待命] 暫無物資需演習。")
        return
    
    m = res.data[0]
    # 🚀 3. 本地先行解析最終直連網址
    total_size, resolved_url = get_target_specs(m['audio_url'])
    total_mb = total_size / (1024 * 1024)
    
    if total_size == 0 or total_mb > 60:
        print(f"🛑 [撤退] 物資體積 ({total_mb:.2f}MB) 超標，不予搬運。")
        return

    # 🚀 4. 分段計算 (採用您選擇的 4.5MB 穩健步調)
    chunk_size = max(5.5 * 1024 * 1024, math.ceil(total_size / 20))
    num_chunks = math.ceil(total_size / chunk_size)
    if not os.path.exists('parts'): os.makedirs('parts')

    print(f"🚀 [演習開始] {m['source_name']} | 總重：{total_mb:.2f}MB | 分段：{num_chunks}")

    # 🚀 5. 序列化擬態搬運
    for i in range(num_chunks):
        if i > 0: time.sleep(random.uniform(8.5, 16.2))
        start = i * chunk_size
        end = min(start + chunk_size - 1, total_size - 1)

        # 一行註解：使用解析後的 resolved_url 避開轉址風險。
        chunk_data = fetch_chunk_via_proxy(resolved_url, start, end, scra_key)
        
        if chunk_data:
            with open(f"parts/part_{i}.bin", "wb") as f: f.write(chunk_data)
            print(f"✅ 片段 {i} 成功。")
        else:
            print(f"❌ [斷供] 片段 {i} 遭拒。")
            return

    # 🚀 6. 縫合、壓縮與 AI 分析
    final_opus = f"RELAY_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{m['source_name']}.opus"
    c_size = assemble_and_compress(m['id'], num_chunks, final_opus, resolved_url)
    
    print(f"🧠 [AI 行動] 呼叫智囊團執行摘要...")
    analysis, _, duration = ai_agent.generate_gold_analysis(final_opus)

    if analysis:
        # 🚀 7. Telegram 報戰
        report_msg = ai_agent.format_mission_report("Relay-V3.4", m['episode_title'], resolved_url, analysis, datetime.now().strftime("%m/%d/%y"), duration, m['source_name'])
        report_msg += f"\n\n📊 [物流數據]\n原始：{total_mb:.2f}MB\n壓縮後：{c_size/(1024*1024):.2f}MB"
        requests.post(f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage", 
                      json={"chat_id": os.environ.get("TELEGRAM_CHAT_ID"), "text": report_msg, "parse_mode": "Markdown"})

    # 🚀 8. 入庫與歸檔
    s3_client.upload_file(final_opus, r2_bucket, final_opus, ExtraArgs={'ContentType': 'audio/ogg'})
    supabase.table("mission_queue").update({"status": "completed", "r2_url": final_opus}).eq("id", m['id']).execute()
    print(f"🏆 [演習達成] 物資已入庫且任務已結案。")
    if os.path.exists(final_opus): os.remove(final_opus)

if __name__ == "__main__":
    run_full_cycle_test()