
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_logistics.py v7.3 (智能網域分流版)
# 任務：1. 雙軌下載：常規 T2 支援 + T1_RESCUE 403 破門救援
#       2. 403 檢舉與規避 3. 擬人化偽裝
# [v7.3 升級] 加入「智能網域分流」機制：擴大掃描池，強制挑選相異網域下載，徹底避開重複敲擊。
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

def get_root_domain(url):
    """提取主網域，將 a.libsyn.com 和 b.libsyn.com 歸類為相同的 libsyn.com"""
    domain = urlparse(url).netloc
    parts = domain.split('.')
    if len(parts) > 2:
        return ".".join(parts[-2:])
    return domain

def run_logistics_mission():
    TARGET_LIMIT = 3 # 🎯 總計最多挑選 3 個不同網域的任務
    SLEEP_MIN, SLEEP_MAX = 180, 360
    
    sb = get_sb(); s3 = get_s3(); bucket = get_secret("R2_BUCKET_NAME")
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 🕵️ 領取黑名單：確保不重複踩雷
    rule_res = sb.table("pod_scra_rules").select("domain").eq("worker_id", "GITHUB_LOGISTICS").execute()
    # 將黑名單轉換為主網域格式
    my_blacklist = [get_root_domain(f"http://{r['domain']}") for r in rule_res.data] if rule_res.data else []

    # 🚀 雙軌查詢邏輯 (擴大掃描池20 +20 筆，方便後續篩選相異網域)
    rescue_query = sb.table("mission_queue").select("*")\
                   .eq("scrape_status", "pending")\
                   .eq("assigned_troop", "T1_RESCUE")\
                   .order("created_at", desc=False).limit(20).execute()
    
    regular_query = sb.table("mission_queue").select("*")\
                    .eq("scrape_status", "success")\
                    .eq("assigned_troop", "T2")\
                    .lte("troop2_start_at", now_iso)\
                    .order("created_at", desc=False).limit(20).execute()
    
    raw_list = (rescue_query.data or []) + (regular_query.data or [])

    # 🛡️ 智能網域分流：從候選名單中，挑選網域不重複的任務
    download_list = []
    visited_domains = set(my_blacklist) # 預先把黑名單當作已造訪過
    
    for task in raw_list:
        root_domain = get_root_domain(task['audio_url'])
        
        if root_domain not in visited_domains:
            download_list.append(task)
            visited_domains.add(root_domain) # 加入集合，同網域下一個就會被跳過
        
        if len(download_list) >= TARGET_LIMIT:
            break

    if download_list:
        print(f"🚛 [物流啟動] 經智能分流，選定 {len(download_list)} 筆相異網域物資準備搬運...")
        for idx, task in enumerate(download_list):
            task_id, audio_url = task['id'], task['audio_url']
            target_domain = urlparse(audio_url).netloc
            troop_type = task.get("assigned_troop", "UNKNOWN")

            try:
                print(f"🎯 [鎖定] 任務類型: {troop_type} | 來源: {target_domain}")
                file_name = f"{datetime.now().strftime('%Y%m%d')}_{str(task_id)[:8]}.opus"
                raw_path, opus_path = f"/tmp/raw_{str(task_id)[:8]}", f"/tmp/{file_name}"
                
                # 🚀 偽裝下載
                with requests.get(audio_url, stream=True, timeout=180, headers=get_headers()) as r:
                    r.raise_for_status()
                    with open(raw_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=16384): f.write(chunk)
                
                if compress_audio(raw_path, opus_path):
                    s3.upload_file(opus_path, bucket, file_name)
                    # 無論原本是 success 還是 pending，成功後一律改為 completed
                    sb.table("mission_queue").update({"status": "completed", "scrape_status": "completed", "r2_url": file_name}).eq("id", task_id).execute()
                    print(f"✅ [成功] {file_name} 已入庫")

            except requests.exceptions.HTTPError as he:
                if he.response.status_code == 403:
                    print(f"🚫 [ROE檢舉] 遭遇 403！標記 domain: {target_domain}")
                    sb.table("pod_scra_rules").insert({"worker_id": "GITHUB_LOGISTICS", "domain": target_domain, "expired_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()}).execute()
                else: print(f"❌ HTTP錯誤: {he}")
            except Exception as e: print(f"❌ 任務潰敗: {e}")
            finally:
                for p in [raw_path, opus_path]:
                    if os.path.exists(p): os.remove(p)
                
            if idx < len(download_list) - 1: time.sleep(random.randint(SLEEP_MIN, SLEEP_MAX))
    else:
        print("☕ [待命] 目前無適合且不在黑名單內的 T2 支援任務或 T1 救援任務。")

if __name__ == "__main__":
    run_logistics_mission()