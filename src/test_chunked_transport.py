# ---------------------------------------------------------
# 本程式碼：src/test_chunked_transport.py v2.0 (全維度偵察搬運版)
# 任務：HEAD 偵察、動態分段、擬態緩衝搬運、二進位縫合與 Opus 轉碼
# ---------------------------------------------------------
import os, requests, time, random, boto3, math, subprocess
from supabase import create_client, Client
from datetime import datetime, timezone

# --- [區塊一：物資偵察模組 (Reconnaissance)] ---
def get_target_specs(url):
    """
    一行註解：透過 HEAD 請求預先獲取檔案規格（大小、類型），作為搬運策略依據。
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebkit/537.36'}
    try:
        # 一行註解：allow_redirects=True 確保能抓到 Megaphone 等跳轉後的最終檔案大小。
        r = requests.head(url, headers=headers, timeout=15, allow_redirects=True)
        size = int(r.headers.get('Content-Length', 0))
        return size
    except Exception as e:
        print(f"⚠️ [預查失敗] 無法獲取物資體積：{e}")
        return 0

# --- [區塊二：物流中繼模組 (Relay)] ---
def fetch_chunk_via_proxy(target_url, start, end, api_key):
    """
    一行註解：利用 WebScraping.ai 的 keep_headers 參數，透傳 Range 標頭進行分段抓取。
    """
    proxy_params = {
        'api_key': api_key,
        'url': target_url,
        'keep_headers': 'true', # 🚀 關鍵：必須保留 Range 標頭，伺服器才會回傳 206
        'proxy': 'residential'  # 建議搬運時使用住宅代理以降低 403 風險
    }
    custom_headers = {
        'Range': f'bytes={start}-{end}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebkit/537.36'
    }
    try:
        resp = requests.get('https://api.webscraping.ai/html', 
                            params=proxy_params, headers=custom_headers, timeout=60)
        return resp.content if resp.status_code in [200, 206] else None
    except Exception:
        return None

# --- [區塊三：縫合與重編模組 (Assembler)] ---
def assemble_and_compress(task_id, chunk_count, final_name):
    """
    一行註解：將分段二進位檔案按序縫合，並調用 FFmpeg 執行 16K/Mono/Opus 高效壓縮。
    """
    temp_raw = f"{task_id}_merged.mp3"
    # 一行註解：二進位無損縫合。
    with open(temp_raw, 'wb') as outfile:
        for i in range(chunk_count):
            part_path = f"parts/part_{i}.bin"
            if os.path.exists(part_path):
                with open(part_path, 'rb') as infile: outfile.write(infile.read())
                os.remove(part_path)

    # 一行註解：FFmpeg 轉碼，-b:a 24k 確保 7MB 以下目標。
    subprocess.run([
        'ffmpeg', '-y', '-i', temp_raw,
        '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k',
        final_name
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(temp_raw): os.remove(temp_raw)
    return os.path.getsize(final_name)

# --- [主演習程序 (Main Expedition)] ---
def run_relay_expedition():
    # 1. 補給與初始化
    scra_key = os.environ.get("WEBSCRAP_API_KEY")
    r2_id, r2_secret = os.environ.get("R2_ACCESS_KEY_ID"), os.environ.get("R2_SECRET_ACCESS_KEY")
    r2_acc, r2_bucket = os.environ.get("R2_ACCOUNT_ID"), os.environ.get("R2_BUCKET_NAME")
    
    s3_client = boto3.client('s3', endpoint_url=f'https://{r2_acc}.r2.cloudflarestorage.com',
                             aws_access_key_id=r2_id, aws_secret_access_key=r2_secret)

    # 🚀 模擬從 Supabase 領取一個實際任務 (此處示範網址)
    target_url = "https://traffic.megaphone.fm/WSJ2187157396.mp3"
    task_id = "TASK_" + datetime.now().strftime('%m%d%H%M')

    # 🚀 2. 前置偵察 (決定搬運策略)
    total_size_bytes = get_target_specs(target_url)
    if total_size_bytes == 0:
        print("🛑 [終止] 無法預查物資規模，放棄出擊。")
        return
    
    total_mb = total_size_bytes / (1024 * 1024)
    print(f"📊 [情報報捷] 物資體積：{total_mb:.2f} MB")

    # 🚀 戰略分流：若檔案太小（<1.2MB）則單次搬運，不分段。
    if total_mb < 1.2:
        print("💡 [策略優化] 物資極輕，切換至單次搬運模式...")
        chunk_size = total_size_bytes
    else:
        chunk_size = 1024 * 1024 # 1MB 標準片段

    num_chunks = math.ceil(total_size_bytes / chunk_size)
    if not os.path.exists('parts'): os.makedirs('parts')

    print(f"🚀 [演習開始] 模式：擬態緩衝分段 | 片段數：{num_chunks} | 預計消耗：{num_chunks} 點")

    # 3. 執行序列化搬運 (擬人化處理)
    for i in range(num_chunks):
        start = i * chunk_size
        end = min(start + chunk_size - 1, total_size_bytes - 1)
        
        # 一行註解：首片段即時抓取，後續片段模擬人類「播放緩衝」抖動。
        if i > 0:
            jitter = random.uniform(4.5, 9.2) 
            print(f"🕒 [擬態緩衝] 等待 {jitter:.2f} 秒以避開偵測...")
            time.sleep(jitter)

        chunk_data = fetch_chunk_via_proxy(target_url, start, end, scra_key)
        
        if chunk_data:
            with open(f"parts/part_{i}.bin", "wb") as f: f.write(chunk_data)
            print(f"✅ 片段 {i} 搬運完成。")
        else:
            print(f"❌ [重大損益] 片段 {i} 遺失，本次演習宣告失敗。")
            return

    # 4. 縫合、壓縮與後置校驗
    final_opus = f"RELAY_{task_id}.opus"
    compressed_size = assemble_and_compress(task_id, num_chunks, final_opus)
    
    # 一行註解：計算最終戰果，評估壓縮比率。
    ratio = (compressed_size / total_size_bytes) * 100
    print(f"📈 [後置校驗] 原始：{total_mb:.2f}MB -> 壓縮後：{compressed_size/(1024*1024):.2f}MB (效率：{ratio:.1f}%)")

    # 5. 物資入庫
    s3_client.upload_file(final_opus, r2_bucket, final_opus, ExtraArgs={'ContentType': 'audio/ogg'})
    print(f"🏆 [演習成功] 物資已入庫：{final_opus}")

if __name__ == "__main__":
    run_relay_expedition()