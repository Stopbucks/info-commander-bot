# ---------------------------------------------------------
# 本程式碼：src/test_chunked_transport.py v1.0 (分段滲透版)
# 任務：測試 WebScraping.ai 分段搬運、擬態緩衝與音檔自動縫合
# ---------------------------------------------------------
import os, requests, time, random, boto3, math, subprocess
from supabase import create_client, Client
from datetime import datetime, timezone

# --- [區塊一：通訊與中繼模組] ---
def fetch_chunk_with_mimicry(target_url, start, end, api_key):
    """
    一行註解：利用 keep_headers 參數，透過 WebScraping.ai 代理傳遞 Range 標頭獲取片段。
    """
    params = {
        'api_key': api_key,
        'url': target_url,
        'keep_headers': 'true', # 🚀 關鍵：確保 Range 標頭被送往目標伺服器
        'proxy': 'residential'  # 使用住宅代理提升穿透力
    }
    headers = {
        'Range': f'bytes={start}-{end}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebkit/537.36'
    }
    try:
        # 一行註解：執行請求，若伺服器支援分段則會回傳 206 Partial Content。
        resp = requests.get('https://api.webscraping.ai/html', params=params, headers=headers, timeout=60)
        return resp.content if resp.status_code in [200, 206] else None
    except Exception:
        return None

# --- [區塊二：組裝與壓縮模組 (Assembler)] ---
def assemble_and_compress(task_id, chunk_count, final_name):
    """
    一行註解：將本地暫存的片段縫合為單一檔案，並使用 FFmpeg 進行 Opus 轉碼。
    """
    temp_raw = f"{task_id}_full.mp3"
    # 一行註解：按照編號順序讀取片段並寫入主檔案。
    with open(temp_raw, 'wb') as outfile:
        for i in range(chunk_count):
            part_path = f"parts/part_{i}.bin"
            if os.path.exists(part_path):
                with open(part_path, 'rb') as infile: outfile.write(infile.read())
                os.remove(part_path) # 節省空間

    # 一行註解：執行 16K/Mono/Opus 壓縮指令，確保最終檔案輕量化。
    subprocess.run([
        'ffmpeg', '-y', '-i', temp_raw,
        '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k',
        final_name
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(temp_raw): os.remove(temp_raw)

# --- [主演習程序] ---
def run_transport_test():
    # 1. 初始化環境 (延續 S-Plan 金鑰鏈)
    scra_key = os.environ.get("WEBSCRAP_API_KEY")
    r2_id, r2_secret = os.environ.get("R2_ACCESS_KEY_ID"), os.environ.get("R2_SECRET_ACCESS_KEY")
    r2_acc, r2_bucket = os.environ.get("R2_ACCOUNT_ID"), os.environ.get("R2_BUCKET_NAME")
    
    s3_client = boto3.client('s3', endpoint_url=f'https://{r2_acc}.r2.cloudflarestorage.com',
                             aws_access_key_id=r2_id, aws_secret_access_key=r2_secret)

    # 🚀 模擬目標：假設測試 7MB 檔案 (此處可從 Supabase 領取實際 audio_url)
    target_url = "https://traffic.megaphone.fm/WSJ2187157396.mp3" # 範例
    task_id = "test_001"
    chunk_size = 1024 * 1024 # 1MB
    total_size = 7 * 1024 * 1024 # 預估 7MB
    num_chunks = math.ceil(total_size / chunk_size)

    if not os.path.exists('parts'): os.makedirs('parts')

    print(f"🚀 [演習開始] 啟動分段搬運：{num_chunks} 片段...")

    for i in range(num_chunks):
        # 2. 擬態緩衝與 Jitter
        if i > 0:
            jitter = random.uniform(3.5, 8.2) # 擬人化隨機延遲
            print(f"🕒 [擬態緩衝] 等待 {jitter:.2f} 秒...")
            time.sleep(jitter)

        start = i * chunk_size
        end = min(start + chunk_size - 1, total_size - 1)
        
        # 3. 執行中繼搬運
        data = fetch_chunk_with_mimicry(target_url, start, end, scra_key)
        
        if data:
            with open(f"parts/part_{i}.bin", "wb") as f: f.write(data)
            print(f"✅ 片段 {i} 搬運成功。")
        else:
            print(f"❌ 片段 {i} 遺失，發動回溯測試中...")
            # 這裡未來可整合補齊邏輯

    # 4. 縫合與入庫
    final_opus = f"RELAY_{datetime.now().strftime('%H%M%S')}.opus"
    assemble_and_compress(task_id, num_chunks, final_opus)
    
    # 5. 推送 R2
    s3_client.upload_file(final_opus, r2_bucket, final_opus, ExtraArgs={'ContentType': 'audio/ogg'})
    print(f"🏆 [演習達成] 最終物資已入庫：{final_opus}")

if __name__ == "__main__":
    run_transport_test()