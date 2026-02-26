# ---------------------------------------------------------
# 本程式碼：src/pod_scra_worker.py v8.1 (大一統混編版)
# 職責：從 mission_queue 領取偵察成功的任務 -> 下載 -> 直送 R2
# ---------------------------------------------------------
import os, time, json, requests, boto3, re, random
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# --- 🛡️ 憑證讀取 ---
def get_secret(key, default=None):
    vault_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(vault_path):
        with open(vault_path, 'r') as f:
            v = json.load(f); return v.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def get_sb(): return create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))

def get_s3():
    return boto3.client('s3', endpoint_url=get_secret("R2_ENDPOINT_URL"),
                        aws_access_key_id=get_secret("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=get_secret("R2_SECRET_ACCESS_KEY"), region_name="auto")

def sanitize_filename(text, max_length=50):
    return re.sub(r'[\\/*?:"<>|]', "", str(text))[:max_length].strip()

# --- ⚔️ 輪值判定 ---
def check_duty(sb: Client, worker_name: str):
    res = sb.table("pod_scra_tactics").select("*").eq("id", 1).execute()
    if not res.data: return False
    active = res.data[0].get("active_worker")
    if active != worker_name:
        print(f"🛌 [待命] 目前執勤部隊為 {active}，{worker_name} 轉為靜默備援。")
        return False
    return True

# --- 🚀 核心搬運邏輯 ---
def run_logistics_mission():
    # === 🛠️ 戰術配置 ===
    WORKER_ID = "GITHUB"        # 👈 GitHub Action 專屬標記
    NEW_LIMIT = 2              # 每次抓 2 筆最新
    OLD_LIMIT = 1              # 每次抓 1 筆最舊
    # ===================

    print(f"🚀 [{WORKER_ID}] 運輸部隊啟動。")
    sb = get_sb(); s3 = get_s3(); bucket = get_secret("R2_BUCKET_NAME")
    
    # 判斷是否為單次執行模式 (GitHub Actions 環境)
    is_gha = os.environ.get("GITHUB_ACTIONS") == "true"

    while True:
        try:
            if not check_duty(sb, WORKER_ID):
                if is_gha: break # GHA 模式下若非執勤則直接結束
                time.sleep(3600); continue

            print(f"🕒 [{WORKER_ID}] 正在領取任務 (配額: {NEW_LIMIT}新 + {OLD_LIMIT}舊)...")
            
            # 1. 領取最新
            new_res = sb.table("mission_queue").select("*") \
                        .eq("scrape_status", "success").eq("status", "pending") \
                        .order("created_at", desc=True).limit(NEW_LIMIT).execute()
            
            # 2. 領取最舊 (排除 ID)
            excluded = [t['id'] for t in new_res.data]
            old_res = sb.table("mission_queue").select("*") \
                        .eq("scrape_status", "success").eq("status", "pending") \
                        .not_.in_("id", excluded) \
                        .order("created_at", desc=False).limit(OLD_LIMIT).execute()
            
            combined = new_res.data + old_res.data
            if not combined:
                print("☕ [物流部] 目前無待搬運物資。")
                if is_gha: break
                time.sleep(3600); continue

            for idx, task in enumerate(combined):
                task_id = task['id']
                audio_url = task['audio_url']
                source = task.get('source_name', 'Unknown')
                title = task.get('episode_title', 'Untitled')
                
                print(f"🚛 [運輸 {idx+1}/{len(combined)}] 鎖定: {title[:20]}")
                
                try:
                    file_name = f"{datetime.now().strftime('%Y%m%d')}_{task_id[:8]}.mp3"
                    temp_path = f"/tmp/{file_name}"
                    
                    # 下載
                    with requests.get(audio_url, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        with open(temp_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                    
                    # 上傳 R2
                    s3.upload_file(temp_path, bucket, file_name)
                    
                    # 結案回填
                    sb.table("mission_queue").update({
                        "status": "completed", 
                        "r2_url": file_name,
                        "recon_persona": f"{WORKER_ID}_Worker_v8.1"
                    }).eq("id", task_id).execute()
                    
                    print(f"✅ [入庫完成] 任務 {task_id}")
                    if os.path.exists(temp_path): os.remove(temp_path)
                    
                    # Jitter 延遲預防封鎖
                    if idx < len(combined) - 1:
                        wait = random.randint(30, 60)
                        print(f"⏳ 隨機喘息 {wait} 秒...")
                        time.sleep(wait)

                except Exception as e:
                    print(f"❌ [任務潰敗] {task_id}: {e}")

            if is_gha: 
                print("🏁 [GHA] 任務批次完成，撤離戰場。")
                break
            
            print(f"🧊 批次完成，休眠 12 小時...")
            time.sleep(12 * 3600)

        except Exception as e:
            print(f"💥 系統異常: {e}")
            if is_gha: break
            time.sleep(300)

if __name__ == "__main__":
    run_logistics_mission()