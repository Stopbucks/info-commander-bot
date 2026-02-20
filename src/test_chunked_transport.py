# ---------------------------------------------------------
# 本程式碼：src/test_chunked_transport.py v4.5 (純代理攻堅版)
# 任務：60MB 門檻、4.5MB 分段、純代理二進位透傳、FFmpeg 縫合、AI 報戰
# ---------------------------------------------------------
import os, requests, time, random, boto3, math, subprocess, urllib3
from supabase import create_client, Client
from datetime import datetime
from podcast_ai_agent import AIAgent 

# 一行註解：禁用代理模式產生的 SSL 安全憑證警告，確保日誌整潔。
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [區塊一：物資規格與直連偵察] ---
def get_target_specs(url):
    """一行註解：執行本地 HEAD 請求以獲取最終直連位址與檔案體積。"""
    stealth_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }
    try:
        r = requests.head(url, headers=stealth_headers, timeout=15, allow_redirects=True)
        return int(r.headers.get('Content-Length', 0)), r.url
    except Exception as e:
        print(f"⚠️ [偵察受阻] {e}")
        return 0, url

# --- [區塊二：純代理物流中繼模組 v4.5] ---
def fetch_chunk_via_pure_proxy(target_url, start, end, api_key):
    """一行註解：透過 WebScraping.ai 8888 端口執行純代理傳輸，確保二進位流不被 HTML 污染。"""
    # 一行註解：將控制參數封裝為密碼，js=false 與 residential 確保高穿透力。
    proxy_params = "js=false&proxy=residential"
    # 一行註解：建構認證代理 URL，採用 Basic Auth 格式。
    proxy_url = f"http://{api_key}:{proxy_params}@proxy.webscraping.ai:8888"
    
    proxies = {"http": proxy_url, "https": proxy_url}
    headers = {
        'Range': f'bytes={start}-{end}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://anchor.fm/'
    }

    try:
        # 一行註解：使用 verify=False 以相容代理商自簽名憑證。
        resp = requests.get(target_url, headers=headers, proxies=proxies, timeout=60, verify=False)
        
        if resp.status_code == 206:
            # 一行註解：執行品質指紋檢驗，若內容太小或含 HTML 標籤則熔斷。
            if b"<html" in resp.content[:100].lower():
                print(f"⚠️ [攔截警報] 代理回傳了 HTML 殼層而非二進位碎片。")
                return None
            return resp.content
        print(f"❌ [狀態異常] 響應碼：{resp.status_code}")
        return None
    except Exception as e:
        print(f"⚠️ [連線崩潰] {e}")
        return None

# --- [區塊三：FFmpeg 縫合與重編模組] ---
def assemble_and_compress(task_id, chunk_count, final_name, source_url):
    """一行註解：合併碎片並執行 16K/Mono/Opus 壓縮，優化 M4A/MP3 索引結構。"""
    ext = ".m4a" if ".m4a" in source_url.lower() else ".mp3"
    temp_raw = f"{task_id}_raw{ext}"
    
    with open(temp_raw, 'wb') as outfile:
        for i in range(chunk_count):
            part_path = f"parts/part_{i}.bin"
            if os.path.exists(part_path):
                with open(part_path, 'rb') as infile: outfile.write(infile.read())
                os.remove(part_path)

    # 一行註解：加入 -movflags faststart，確保音訊在 R2 預覽時能即時播放。
    subprocess.run([
        'ffmpeg', '-y', '-err_detect', 'ignore_err', '-i', temp_raw,
        '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k',
        '-movflags', 'faststart', final_name
    ], capture_output=True)
    
    if os.path.exists(temp_raw): os.remove(temp_raw)
    return os.path.getsize(final_name)

# --- [主演習程序] ---
def run_full_cycle_test():
    # 1. 初始化補給線
    scra_key = os.environ.get("WEBSCRAP_API_KEY")
    supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    ai_agent = AIAgent()
    s3_client = boto3.client('s3', endpoint_url=f"https://{os.environ.get('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
                             aws_access_key_id=os.environ.get('R2_ACCESS_KEY_ID'), 
                             aws_secret_access_key=os.environ.get('R2_SECRET_ACCESS_KEY'))

    # 🚀 2. 領取待命物資
    res = supabase.table("mission_queue").select("*").eq("status", "pending") \
        .not_.is_("audio_url", "null").order("created_at", desc=True).limit(1).execute()

    if not res.data: return print("☕ [待命] 無演習物資。")
    m = res.data[0]
    
    # 🚀 3. 先行解析直連位址 (關鍵斥候行動)
    total_size, resolved_url = get_target_specs(m['audio_url'])
    total_mb = total_size / (1024 * 1024)
    
    if total_size == 0 or total_mb > 60:
        return print(f"🛑 [撤退] 體積 ({total_mb:.2f}MB) 超標或無效。")

    # 🚀 4. 分段決策 (採用 4.5MB 穩健載荷)
    chunk_size = max(4.5 * 1024 * 1024, math.ceil(total_size / 15))
    num_chunks = math.ceil(total_size / chunk_size)
    if not os.path.exists('parts'): os.makedirs('parts')

    print(f"🚀 [演習啟動] {m['source_name']} | 總重：{total_mb:.2f}MB | 分段：{num_chunks}")

    # 🚀 5. 序列化代理搬運
    for i in range(num_chunks):
        if i > 0: time.sleep(random.uniform(7.5, 12.5))
        start, end = i * chunk_size, min((i + 1) * chunk_size - 1, total_size - 1)

        # 一行註解：發動 v4.5 純代理模式搬運。
        chunk_data = fetch_chunk_via_pure_proxy(resolved_url, start, end, scra_key)
        
        if chunk_data:
            with open(f"parts/part_{i}.bin", "wb") as f: f.write(chunk_data)
            print(f"✅ 片段 {i} 成功。")
        else:
            return print(f"❌ [中斷] 片段 {i} 獲取失敗，執行熔斷。")

    # 🚀 6. 縫合分析與報戰
    final_opus = f"RELAY_V45_{datetime.now().strftime('%Y%m%d')}_{m['source_name']}.opus"
    c_size = assemble_and_compress(m['id'], num_chunks, final_opus, resolved_url)
    analysis, _, duration = ai_agent.generate_gold_analysis(final_opus)

    if analysis:
        report = ai_agent.format_mission_report("Proxy-V4.5", m['episode_title'], resolved_url, analysis, datetime.now().strftime("%m/%d/%y"), duration, m['source_name'])
        report += f"\n\n📊 [數據]\n原始：{total_mb:.2f}MB\n壓縮：{c_size/(1024*1024):.2f}MB"
        requests.post(f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage", 
                      json={"chat_id": os.environ.get("TELEGRAM_CHAT_ID"), "text": report, "parse_mode": "Markdown"})

    # 🚀 7. 入庫歸檔
    s3_client.upload_file(final_opus, os.environ.get('R2_BUCKET_NAME'), final_opus, ExtraArgs={'ContentType': 'audio/ogg'})
    supabase.table("mission_queue").update({"status": "completed", "r2_url": final_opus}).eq("id", m['id']).execute()
    print(f"🏆 [演習達成] 任務結案。")
    if os.path.exists(final_opus): os.remove(final_opus)

if __name__ == "__main__":
    run_full_cycle_test()