# ---------------------------------------------------------
# 本程式碼：src/pod_scra_fallback.py v1.0
# 任務：領取 3 筆待命任務 -> 擬態下載 -> Opus 轉碼 -> 直送 R2
# ---------------------------------------------------------
import os, requests, boto3, subprocess, random, time
from supabase import create_client, Client
from datetime import datetime
from podcast_ai_agent import AIAgent

def run_fallback_transport():
    # 1. 讀取法定金鑰
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    r2_id = os.environ.get("R2_ACCESS_KEY_ID")
    r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    r2_account_id = os.environ.get("R2_ACCOUNT_ID")
    r2_bucket = os.environ.get("R2_BUCKET_NAME", "pod-scra-vault")

    if not all([sb_url, sb_key, r2_id, r2_secret, r2_account_id]):
        print("❌ [據點] 環境變數不全，撤退。")
        return

    # 初始化
    supabase: Client = create_client(sb_url, sb_key)
    s3_client = boto3.client(
        's3', endpoint_url=f'https://{r2_account_id}.r2.cloudflarestorage.com',
        aws_access_key_id=r2_id, aws_secret_access_key=r2_secret, region_name='auto'
    )
    ai_agent = AIAgent()

    # 2. 領取 3 筆待命中的任務 (狀態為 pending 且 scrape_status 為 success)
    res = supabase.table("mission_queue").select("*")\
        .eq("status", "pending")\
        .eq("scrape_status", "success")\
        .limit(3).execute()
    
    if not res.data:
        print("☕ [據點] 目前無須處理的緊急任務。")
        return

    for index, m in enumerate(res.data):
        audio_url = m.get('audio_url')
        raw_file = f"fb_raw_{index}.mp3"
        opus_file = f"fb_proc_{index}.opus"
        r2_name = f"FB_{datetime.now().strftime('%Y%m%d_%H%M')}_{m.get('source_name')}.opus"

        try:
            # 擬態下載 (使用與 transport 相同的偽裝標頭)
            print(f"📥 [據點下載] 獲取物資：{m.get('source_name')}")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
            with requests.get(audio_url, stream=True, timeout=300, headers=headers) as r:
                r.raise_for_status()
                with open(raw_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

            # Opus 轉碼
            subprocess.run(['ffmpeg', '-y', '-i', raw_file, '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k', opus_file], check=True)

            # 直送 R2 與 AI 摘要
            s3_client.upload_file(opus_file, r2_bucket, r2_name, ExtraArgs={'ContentType': 'audio/ogg'})
            analysis, _, duration = ai_agent.generate_gold_analysis(opus_file)

            # 更新回報
            if analysis:
                report_msg = ai_agent.format_mission_report("Fallback", m['episode_title'], audio_url, analysis, datetime.now().strftime("%m/%d/%y"), duration, m['source_name'])
                requests.post(f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage", 
                               json={"chat_id": os.environ.get('TELEGRAM_CHAT_ID'), "text": report_msg, "parse_mode": "Markdown"})

            supabase.table("mission_queue").update({"status": "completed", "r2_url": r2_name, "mission_type": "fallback_finished"}).eq("id", m['id']).execute()
            print(f"🏆 [據點成功] 任務 {m['id']} 已轉運。")

        except Exception as e:
            print(f"⚠️ [據點失敗]：{e}")
        finally:
            for f in [raw_file, opus_file]:
                if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    run_fallback_transport()