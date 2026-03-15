# ---------------------------------------------------------
# 程式碼：src/pod_scra_intel_r2.py  (S-Plan 兵工廠與倉儲模組)
# 任務：專職底層基礎設施 (R2 連線、檔案上下傳、ffmpeg 壓縮改裝)
# ---------------------------------------------------------

import os, requests, gc, subprocess, boto3
import imageio_ffmpeg   

def get_s3_client():
    return boto3.client('s3', endpoint_url=os.environ.get("R2_ENDPOINT_URL"),
                        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"), region_name="auto")

def upload_to_r2(local_path, filename):
    s3 = get_s3_client()
    s3.upload_file(local_path, os.environ.get("R2_BUCKET_NAME"), filename)

def download_from_r2(filename, local_path):
    url = f"{os.environ.get('R2_PUBLIC_URL')}/{filename}"
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024): f.write(chunk)

def compress_task_to_opus(task_id, raw_filename):
    ext = os.path.splitext(raw_filename)[1].lower() or '.mp3'
    tmp_in = f"/tmp/in_{task_id[:8]}{ext}"
    tmp_out = f"/tmp/out_{task_id[:8]}.opus"
    new_name = f"opt_{task_id[:8]}.opus"
    
    try:
        download_from_r2(raw_filename, tmp_in)
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg_exe, '-y', '-i', tmp_in, '-ar', '16000', '-ac', '1', 
               '-c:a', 'libopus', '-b:a', '16k', '-vbr', 'off', 
               '-compression_level', '0', '-preset', 'superfast', tmp_out]
        subprocess.run(cmd, check=True, capture_output=True)
        
        upload_to_r2(tmp_out, new_name)
        return True, new_name
        
    except Exception as e:
        print(f"❌ [改裝失敗]: {e}")
        return False, None
    finally:
        for f in [tmp_in, tmp_out]:
            if os.path.exists(f): os.remove(f)
        gc.collect()