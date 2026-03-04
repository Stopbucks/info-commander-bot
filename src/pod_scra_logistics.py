

# ---------------------------------------------------------
# 本程式碼：src/pod_scra_logistics.py v7.0 (特種武裝版)
# 任務：1. 僅下載 T2 通行證任務 2. 403 檢舉與規避 3. 擬人化偽裝
# ---------------------------------------------------------
import os, time, random, requests, boto3, subprocess, json
from datetime import datetime, timezone, timedelta
from supabase import create_client
from urllib.parse import urlparse

def get_secret(k): return os.environ.get(k)
def get_sb(): return create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
def get_s3():
    return boto3.client('s3', endpoint_url=get_secret("R2_ENDPOINT_URL"),
                        aws_access_key_id=get_secret("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=get_secret("R2_SECRET_ACCESS_KEY"), region_name="auto")

# 🎖️ 新增：擬人化偽裝標頭
def get_headers():
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    return {"User-Agent": random.choice(ua_list)}

def compress_audio(input_path, output_path):
    try:
        subprocess.run(['ffmpeg', '-y', '-i', input_path, '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k', output_path], 
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except: return False

def run_logistics_mission():
    NEW_LIMIT, OLD_LIMIT = 2, 1
    SLEEP_MIN, SLEEP_MAX = 180, 360
    
    sb = get_sb(); s3 = get_s3(); bucket = get_secret("R2_BUCKET_NAME")
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 🕵️ 領取黑名單：確保不重複踩雷
    rule_res = sb.table("pod_scra_rules").select("domain").eq("worker_id", "GITHUB_LOGISTICS").execute()
    my_blacklist = [r['domain'] for r in rule_res.data] if rule_res.data else []

    # 1. 領取 T2 任務 (排除 T1 禁運品)
    query_base = sb.table("mission_queue").select("*")\
                   .eq("scrape_status", "success")\
                   .eq("status", "pending")\
                   .eq("assigned_troop", "T2")\
                   .lte("troop2_start_at", now_iso)
    
    new_res = query_base.order("created_at", desc=True).limit(NEW_LIMIT).execute()
    excluded = [t['id'] for t in new_res.data] if new_res.data else []
    old_res = query_base.not_.in_("id", excluded).order("created_at", desc=False).limit(OLD_LIMIT).execute()
    
    download_list = (new_res.data or []) + (old_res.data or [])

    if download_list:
        print(f"🚛 [物流啟動] 準備搬運 {len(download_list)} 筆 T2 物資...")
        for idx, task in enumerate(download_list):
            task_id, audio_url = task['id'], task['audio_url']
            target_domain = urlparse(audio_url).netloc
            
            # 🛡️ 戰術規避
            if any(b in target_domain for b in my_blacklist):
                print(f"⏩ [避戰] {target_domain} 處於黑名單，跳過。")
                continue

            try:
                file_name = f"{datetime.now().strftime('%Y%m%d')}_{task_id[:8]}.opus"
                raw_path, opus_path = f"/tmp/raw_{task_id}", f"/tmp/{file_name}"
                
                # 🚀 偽裝下載
                with requests.get(audio_url, stream=True, timeout=180, headers=get_headers()) as r:
                    r.raise_for_status()
                    with open(raw_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=16384): f.write(chunk)
                
                if compress_audio(raw_path, opus_path):
                    s3.upload_file(opus_path, bucket, file_name)
                    sb.table("mission_queue").update({"status": "completed", "scrape_status": "completed", "r2_url": file_name}).eq("id", task_id).execute()
                    print(f"✅ [成功] {file_name} 已入庫")

            except requests.exceptions.HTTPError as he:
                if he.response.status_code == 403:
                    print(f"🚫 [ROE檢舉] 遭遇 403！標記 domain: {target_domain}")
                    # 檢舉網域，讓 Vercel 鎖定 17 天
                    sb.table("pod_scra_rules").insert({"worker_id": "GITHUB_LOGISTICS", "domain": target_domain, "expired_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()}).execute()
                    # 不用中斷整個 GITHUB 任務，但跳過當前網域
                else: print(f"❌ HTTP錯誤: {he}")
            except Exception as e: print(f"❌ 任務潰敗: {e}")
            finally:
                for p in [raw_path, opus_path]:
                    if os.path.exists(p): os.remove(p)
                
            if idx < len(download_list) - 1: time.sleep(random.randint(SLEEP_MIN, SLEEP_MAX))