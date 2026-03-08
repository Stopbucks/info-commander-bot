# ---------------------------------------------------------
# 程式碼：src/pod_scra_intel_trans.py  (S-Plan Fortress v4.3)
# 任務：專職物流引擎、 ffmpeg 壓縮 ； boto3 - R2底層溝通
# 適用： RENDER & KOYEB (512 MB)
# 修改：從app.py 獨立，物流邏輯封裝
# ---------------------------------------------------------

import os, requests, time, random, gc, subprocess, boto3
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

def get_s3_client():
    """建立 S3 連線客戶端"""
    return boto3.client('s3', endpoint_url=os.environ.get("R2_ENDPOINT_URL"),
                        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"), region_name="auto")

def upload_to_r2(local_path, filename):
    """將加工物資回傳 R2 倉庫"""
    s3 = get_s3_client()
    s3.upload_file(local_path, os.environ.get("R2_BUCKET_NAME"), filename)

def download_from_r2(filename, local_path):
    """透過公共 URL 快速提取 R2 物資"""
    url = f"{os.environ.get('R2_PUBLIC_URL')}/{filename}"
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024): f.write(chunk)

def compress_task_to_opus(task_id, raw_filename):
    """🛠️ 鋼鐵改裝：將 MP3 轉為 AI 專用極輕量 Opus"""
    tmp_in, tmp_out = f"/tmp/in_{task_id[:8]}.mp3", f"/tmp/out_{task_id[:8]}.opus"
    new_name = f"opt_{task_id[:8]}.opus"
    try:
        download_from_r2(raw_filename, tmp_in)
        # 🚀 鋼鐵指令：Mono, 16k, libopus, 16kbps
        cmd = ['ffmpeg', '-y', '-i', tmp_in, '-ar', '16000', '-ac', '1', 
               '-c:a', 'libopus', '-b:a', '16k', '-vbr', 'off', 
               '-compression_level', '0', '-preset', 'superfast', tmp_out]
        subprocess.run(cmd, check=True, capture_output=True)
        upload_to_r2(tmp_out, new_name)
        return True, new_name
    except Exception as e:
        print(f"❌ [改裝失敗]: {e}"); return False, None
    finally:
        for f in [tmp_in, tmp_out]:
            if os.path.exists(f): os.remove(f)
        gc.collect()

def execute_fortress_stages(sb, config, s_log_func, trigger_intel_func, get_s3_func, officers_list):
    """🚛 執行全階段物流巡邏"""
    now_iso = datetime.now(timezone.utc).isoformat(); worker_id = config["WORKER_ID"]
    try:
        # --- 階段 1：心跳與簽到 ---
        t_res = sb.table("pod_scra_tactics").select("*").eq("id", 1).single().execute()
        if not t_res.data: return
        tactic = t_res.data
        health = tactic.get('workers_health', {}) or {}
        health[worker_id] = now_iso
        sb.table("pod_scra_tactics").update({"last_heartbeat_at": now_iso, "workers_health": health}).eq("id", 1).execute()
        s_log_func(sb, "HEARTBEAT", "SUCCESS", f"💓 {worker_id} 心跳簽到")

        # --- 階段 2：發動 AI 加工鏈 ---
        trigger_intel_func(sb)

        # --- 階段 3：主將物流判定與 T2 下載 ---
        if tactic['active_worker'] == worker_id:
            run_logistics_engine(sb, config, now_iso, get_s3_func, s_log_func)
    except Exception as e:
        s_log_func(sb, "SYSTEM", "ERROR", f"💥 運輸異常: {str(e)}")

def run_logistics_engine(sb, config, now_iso, get_s3_func, s_log_func):
    """負責重型 T2 物資的自動入庫"""
    query = sb.table("mission_queue").select("*, mission_program_master(*)").eq("scrape_status", "success").is_("r2_url", "null").lte("troop2_start_at", now_iso).order("created_at", desc=True).limit(2)
    tasks = query.execute().data or []
    if not tasks: return
    s3 = get_s3_func(); bucket = os.environ.get("R2_BUCKET_NAME")
    for m in tasks:
        f_url = m.get('audio_url'); ext = os.path.splitext(urlparse(f_url).path)[1] or ".mp3"; tmp_path = f"/tmp/dl_{m['id'][:8]}{ext}"
        try:
            with requests.get(f_url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(tmp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=64*1024): f.write(chunk)
            s3.upload_file(tmp_path, bucket, os.path.basename(tmp_path))
            sb.table("mission_queue").update({"scrape_status": "completed", "r2_url": os.path.basename(tmp_path)}).eq("id", m['id']).execute()
            s_log_func(sb, "DOWNLOAD", "SUCCESS", f"✅ 物資入庫: {m['id'][:8]}")
        except Exception as e: s_log_func(sb, "DOWNLOAD", "ERROR", f"❌ 搬運失敗: {str(e)}")
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)
            gc.collect()