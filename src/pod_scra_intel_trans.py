# ---------------------------------------------------------
# 程式碼：src/pod_scra_intel_trans.py  (S-Plan Fortress v4.3)
# 任務：專職物流引擎、 ffmpeg 壓縮 ； boto3 - R2底層溝通
# 適用： RENDER & KOYEB (512 MB)
# 修改：從app.py 獨立，物流邏輯封裝
# ---------------------------------------------------------

# ---------------------------------------------------------
import os, requests, time, random, gc, subprocess, boto3
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

def get_s3_client():
    """建立並回傳 S3 標準連線客戶端"""
    return boto3.client('s3', 
        endpoint_url=os.environ.get("R2_ENDPOINT_URL"),
        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
        region_name="auto"
    )

def upload_to_r2(local_path, filename):
    """將本地加工後的檔案上傳至 R2 指定倉庫"""
    s3 = get_s3_client() # 🚀 獲取連線金鑰
    s3.upload_file(local_path, os.environ.get("R2_BUCKET_NAME"), filename)

def download_from_r2(filename, local_path):
    """透過 Public URL 快速提取 R2 倉庫中的原始物資"""
    url = f"{os.environ.get('R2_PUBLIC_URL')}/{filename}" # 🚀 構建下載路徑
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status() # 🚀 確保下載請求成功
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024): f.write(chunk)

def compress_task_to_opus(task_id, raw_filename):
    """🛠️ 鋼鐵壓縮：將 MP3 轉為 16k Mono Opus (節省內存專用)"""
    tmp_in = f"/tmp/in_{task_id[:8]}.mp3" # 🚀 本地原始暫存路徑
    tmp_out = f"/tmp/out_{task_id[:8]}.opus" # 🚀 改裝後物資路徑
    new_name = f"opt_{task_id[:8]}.opus" # 🚀 回傳倉庫的新檔名

    try:
        print(f"📥 [物流改裝] 開始下載原始物資...")
        download_from_r2(raw_filename, tmp_in) # 🚀 提取 MP3 

        # 執行窄化壓縮：16000Hz、單聲道、16kbps (訪談識別最優解)
        cmd = [
            'ffmpeg', '-y', '-i', tmp_in,
            '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '16k',
            '-vbr', 'off', '-compression_level', '0', '-preset', 'superfast',
            tmp_out
        ]
        # 🚀 啟動 FFmpeg 執行緒並等待完工
        subprocess.run(cmd, check=True, capture_output=True)

        print(f"📤 [物流改裝] 加工完成，正在同步至 R2 倉庫...")
        upload_to_r2(tmp_out, new_name) # 🚀 回傳 R2
        return True, new_name

    except Exception as e:
        print(f"❌ [物流改裝失敗]: {e}")
        return False, None

    finally:
        # 🚀 無論成功或失敗，強制清理磁碟暫存防止爆倉
        for f in [tmp_in, tmp_out]:
            if os.path.exists(f): 
                try: os.remove(f)
                except: pass
        gc.collect() # 🚀 釋放 Python 內存指標

#---堡壘運輸任務(心跳、黑名單)階段---

def execute_fortress_stages(sb, config, s_log_func, trigger_intel_func, get_s3_func, officers_list):
    """🚛 執行全階段物流：包含心跳、同步與情報鏈發動"""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    worker_id = config["WORKER_ID"]

    try:
        # --- 階段 1：戰略簽到與黑名單同步 ---
        t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
        if not t_res.data: return
        tactic = t_res.data # 🚀 讀取當前全局戰術指令

        health = tactic.get('workers_health', {}) or {}
        health[worker_id] = now_iso # 🚀 更新當前節點健康狀態
        sb.table("pod_scra_tactics").update({"last_heartbeat_at": now_iso, "workers_health": health}).eq("id", 1).execute()

        rule_res = sb.table("pod_scra_rules").select("domain").eq("worker_id", worker_id).execute()
        my_blacklist = [r['domain'] for r in rule_res.data] if rule_res.data else [] # 🚀 加載防 403 黑名單
        s_log_func(sb, "HEARTBEAT", "SUCCESS", f"💓 {worker_id} 心跳簽到 (禁區數: {len(my_blacklist)})")

        # --- 階段 2：跨部隊協作 (Call Back to app.py -> core.py) ---
        trigger_intel_func(sb) # 🚀 點火執行 AI 情報加工任務

        # --- 階段 3：重型物流判定 (主將才可下載物資) ---
        if tactic['active_worker'] != worker_id:
            print(f"🛌 [{worker_id}] 處於後援狀態，跳過重型物資下載。")
            return

        # --- 階段 4：啟動重型物流引擎 ---
        run_logistics_engine(sb, config, my_blacklist, now_iso, get_s3_func, s_log_func)

    except Exception as e:
        s_log_func(sb, "SYSTEM", "ERROR", f"💥 運輸中樞異常: {str(e)}")

def run_logistics_engine(sb, config, my_blacklist, now_iso, get_s3_func, s_log_func):
    """專職 T2 物資的自動提取與入庫"""
    query = sb.table("mission_queue").select("*, mission_program_master(*)") \
            .eq("scrape_status", "success") \
            .is_("r2_url", "null") \
            .is_("skip_reason", "null") \
            .lte("troop2_start_at", now_iso) \
            .order("created_at", desc=True).limit(2) # 🚀 每次領取 2 件新物資
    
    tasks = query.execute().data or []
    if not tasks: return print("☕ 戰區物流暫無待領物資。")

    s3 = get_s3_func(); bucket = os.environ.get("R2_BUCKET_NAME")
    for idx, m in enumerate(tasks):
        f_url = m.get('audio_url')
        if not f_url or any(b in urlparse(f_url).netloc for b in my_blacklist): continue # 🚀 規避禁區
        
        ext = os.path.splitext(urlparse(f_url).path)[1] or ".mp3" # 🚀 動態識別格式
        tmp_path = f"/tmp/dl_{m['id'][:8]}{ext}" # 🚀 建立下載緩衝
        try:
            with requests.get(f_url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(tmp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=64*1024): f.write(chunk)
            
            file_name = os.path.basename(tmp_path)
            s3.upload_file(tmp_path, bucket, file_name) # 🚀 送入倉庫
            sb.table("mission_queue").update({"scrape_status": "completed", "r2_url": file_name}).eq("id", m['id']).execute()
            s_log_func(sb, "DOWNLOAD", "SUCCESS", f"✅ 物資入庫: {file_name}")
        except Exception as e:
            s_log_func(sb, "DOWNLOAD", "ERROR", f"❌ 搬運失敗: {str(e)}")
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path) # 🚀 清理磁碟
            gc.collect() # 🚀 強制回收內存