
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_logistics.py v6.2 (旗艦壓縮版)
# 任務：1. 下載(2新+1舊)並壓縮 2. 補救 R2 舊檔(2筆) 3. 擬人避震控制
# ---------------------------------------------------------
import os, time, random, requests, boto3, subprocess
from datetime import datetime, timezone
from supabase import create_client

def get_secret(k): return os.environ.get(k)
def get_sb(): return create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
def get_s3():
    return boto3.client('s3', endpoint_url=get_secret("R2_ENDPOINT_URL"),
                        aws_access_key_id=get_secret("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=get_secret("R2_SECRET_ACCESS_KEY"), region_name="auto")

def compress_audio(input_path, output_path):
    """🚀 強制執行 16K/mono/Opus 壓縮指令"""
    try:
        subprocess.run([
            'ffmpeg', '-y', '-i', input_path,
            '-ar', '16000', '-ac', '1', 
            '-c:a', 'libopus', '-b:a', '24k', 
            output_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"❌ 壓縮失敗: {e}"); return False

def run_logistics_mission():
    # === 🛠️ 戰術控制面板 (Commander Control Panel) ===
    # A. 下載配置 (控制新舊集數比例)
    NEW_LIMIT = 2                # 每次抓 2 筆最新
    OLD_LIMIT = 1                # 每次抓 1 筆最舊補漏
    
    # B. 壓縮配置 (針對已在 R2 但非 Opus 的舊檔)
    RESCUE_COMPRESS_LIMIT = 2    # 每次補救壓縮 2 筆
    
    # C. 避震配置
    SLEEP_MIN, SLEEP_MAX = 180, 360  # 下載完一筆後休息時間 (3~6分鐘)
    # ===============================================

    # 🚀 Jitter：啟動前隨機冷卻
    init_wait = random.randint(10, 45)
    print(f"🕒 [物流避震] 啟動前冷卻 {init_wait} 秒...")
    time.sleep(init_wait)

    sb = get_sb(); s3 = get_s3(); bucket = get_secret("R2_BUCKET_NAME")
    now_iso = datetime.now(timezone.utc).isoformat()
    print(f"🚛 [GITHUB 壓縮物流兵 v6.2] 啟動作業...")

    # =========================================================
    # 🎯 任務一：執行【2新+1舊】下載與壓縮
    # =========================================================
    # 1. 領取最新
    new_res = sb.table("mission_queue").select("*")\
                .eq("scrape_status", "success").eq("status", "pending")\
                .lte("troop2_start_at", now_iso)\
                .order("created_at", desc=True).limit(NEW_LIMIT).execute()
    
    # 2. 領取最舊 (排除 ID)
    excluded = [t['id'] for t in new_res.data] if new_res.data else []
    old_res = sb.table("mission_queue").select("*")\
                .eq("scrape_status", "success").eq("status", "pending")\
                .lte("troop2_start_at", now_iso)\
                .not_.in_("id", excluded)\
                .order("created_at", desc=False).limit(OLD_LIMIT).execute()
    
    download_list = (new_res.data or []) + (old_res.data or [])

    if download_list:
        print(f"📦 [下載清單] 發現 {len(download_list)} 筆到期物資 (新:{len(new_res.data or [])}, 舊:{len(old_res.data or [])})")
        for idx, task in enumerate(download_list):
            task_id = task['id']
            audio_url = task['audio_url']
            try:
                file_name = f"{datetime.now().strftime('%Y%m%d')}_{task_id[:8]}.opus"
                raw_path, opus_path = f"/tmp/raw_{task_id}", f"/tmp/{file_name}"
                
                print(f"🚀 [下載中 {idx+1}/{len(download_list)}] 鎖定: {task_id[:8]}")
                with requests.get(audio_url, stream=True, timeout=180) as r:
                    r.raise_for_status()
                    with open(raw_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                
                if compress_audio(raw_path, opus_path):
                    s3.upload_file(opus_path, bucket, file_name)
                    sb.table("mission_queue").update({
                        "status": "completed", "scrape_status": "completed",
                        "r2_url": file_name, "recon_persona": "GHA_v6.2_Opus"
                    }).eq("id", task_id).execute()
                    print(f"✅ [入庫成功] {file_name}")
                
                if os.path.exists(raw_path): os.remove(raw_path)
                if os.path.exists(opus_path): os.remove(opus_path)
                
                if idx < len(download_list) - 1:
                    wait = random.randint(SLEEP_MIN, SLEEP_MAX)
                    print(f"⏳ [擬人避震] 休息 {wait} 秒...")
                    time.sleep(wait)
            except Exception as e:
                print(f"❌ [任務潰敗] {task_id}: {e}")
    else:
        print("☕ [下載部] 目前無到期待搬運任務。")

    # =========================================================
    # 🎯 任務二：補救 R2 舊大檔 (改為輕量 Opus)
    # =========================================================
    print(f"\n🧹 [倉庫優化] 掃描 R2 舊檔 (限額: {RESCUE_COMPRESS_LIMIT})...")
    rescue_res = sb.table("mission_queue").select("*")\
                   .eq("status", "completed").not_.like("r2_url", "%.opus")\
                   .order("created_at", desc=False).limit(RESCUE_COMPRESS_LIMIT).execute()

    for idx, old_task in enumerate(rescue_res.data or []):
        old_id = old_task['id']
        old_url = old_task.get('audio_url')
        if not old_url: continue

        try:
            print(f"🔄 [補救壓縮 {idx+1}] 正在轉換舊檔: {old_id[:8]}")
            opus_file = f"{datetime.now().strftime('%Y%m%d')}_{old_id[:8]}.opus"
            tmp_raw, tmp_opus = f"/tmp/rescue_{old_id}", f"/tmp/{opus_file}"

            with requests.get(old_url, stream=True, timeout=180) as r:
                r.raise_for_status()
                with open(tmp_raw, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

            if compress_audio(tmp_raw, tmp_opus):
                s3.upload_file(tmp_opus, bucket, opus_file)
                sb.table("mission_queue").update({"r2_url": opus_file}).eq("id", old_id).execute()
                print(f"✅ [補救成功] {old_id[:8]} 已轉為輕量 Opus。")

            if os.path.exists(tmp_raw): os.remove(tmp_raw)
            if os.path.exists(tmp_opus): os.remove(tmp_opus)
            
            # 🚀 序列處理避震：增加處理韌性 (15~30秒，不佔用面板空間)
            time.sleep(random.randint(15, 30))
        except Exception as e:
            print(f"⚠️ [補救異常] {old_id}: {e}")

if __name__ == "__main__":
    run_logistics_mission()