
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v0.91 (法定標籤校準版)
# 任務：領取 3新 + 2舊 任務 -> FFmpeg 壓縮 -> 搬運與 AI 摘要
# 修正：精準對位 GitHub Secrets 標籤 R2_SECRET_ACCESS_KEY
# ---------------------------------------------------------

import os, requests, time, random, boto3, subprocess
from supabase import create_client, Client
from datetime import datetime
from podcast_ai_agent import AIAgent 

def run_transport_and_report():
    # 1. 讀取補給金鑰 (根據法定清單校準)
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    r2_id = os.environ.get("R2_ACCESS_KEY_ID")
    # 🚀 修正：對位法定清單中的名稱 (原為 r2_secret，導致 LOG 報錯)
    r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY") 
    r2_account_id = os.environ.get("R2_ACCOUNT_ID")
    r2_bucket = os.environ.get("R2_BUCKET_NAME", "pod-scra-vault") # 優先使用 Secret 定義
    
    # 2. 安全性檢查：確保所有傳輸通道皆有動力
    if not all([sb_url, sb_key, r2_id, r2_secret, r2_account_id]):
        print(f"❌ [傳輸兵] 環境變數不齊全。檢查結果: ID:{bool(r2_id)}, Secret:{bool(r2_secret)}, Account:{bool(r2_account_id)}")
        return

    # 初始化組件
    supabase: Client = create_client(sb_url, sb_key)
    ai_agent = AIAgent() 
    s3_client = boto3.client(
        's3',
        endpoint_url=f'https://{r2_account_id}.r2.cloudflarestorage.com',
        aws_access_key_id=r2_id,
        aws_secret_access_key=r2_secret, 
        region_name='auto' # 🚀 增加：明確指定 region 提高連線成功率
    )

    # --- 區塊：3新 + 2舊 混編領取邏輯 (不變，維持優良戰術) ---
    new_m = supabase.table("mission_queue").select("*") \
        .filter("status", "eq", "pending") \
        .or_("scrape_status.eq.success,scrape_status.eq.manual_check") \
        .order("created_at", desc=True).limit(3).execute()
    
    picked_ids = [m['id'] for m in new_m.data]
    old_m = supabase.table("mission_queue").select("*") \
        .filter("status", "eq", "pending") \
        .or_("scrape_status.eq.success,scrape_status.eq.manual_check") \
        .not_.in_("id", picked_ids) \
        .order("created_at", desc=False).limit(2).execute()

    all_missions = new_m.data + old_m.data
    
    if not all_missions:
        print("☕ [待命] 倉庫暫無待搬運物資。")
        return

    print(f"📦 [裝載] 混合領取完成：新物資 {len(new_m.data)} 筆，舊物資 {len(old_m.data)} 筆。")

    # 🚀 啟動多任務處理流水線
    for index, mission_data in enumerate(all_missions):
        # A. 任務間大抖動 (保持穩定性)
        if index > 0:
            task_gap = random.randint(120, 300)
            print(f"⏳ [休息] 為避開頻率限制，等待 {task_gap//60} 分鐘...")
            time.sleep(task_gap)

        source_name = mission_data.get('source_name', 'unknown')
        audio_url = mission_data.get('audio_url')
        episode_title = mission_data.get('episode_title', 'Untitled')
        provider_info = mission_data.get('used_provider', 'Legacy/RSS')
        
        if not audio_url:
            print(f"⚠️ 任務 {mission_data['id']} 無音訊網址，跳過。")
            continue

        raw_file = f"raw_{index}.mp3"
        compressed_file = f"proc_{index}.opus"
        r2_file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source_name}.opus"

        try:
            # 🚀 搬運工隨機等待
            jitter_sleep = random.randint(5, 15)
            print(f"🕒 [偽裝休眠] 正在搬運來自 {provider_info} 的物資，等待 {jitter_sleep} 秒...")
            time.sleep(jitter_sleep)

            # 3. 流式下載處理
            print(f"📥 [下載中] 正在獲取：{source_name}...")
            with requests.get(audio_url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(raw_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            
            # --- 核心：FFmpeg 壓縮技術 (16K/Mono/Opus) ---
            print(f"🗜️ [壓縮中] 執行高效率轉碼...")
            # 一行註解：降採樣並轉為單聲道 Opus，極大化節省 R2 空間。
            subprocess.run([
                'ffmpeg', '-y', '-i', raw_file,
                '-ar', '16000', '-ac', '1', '-c:a', 'libopus', '-b:a', '24k',
                compressed_file
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(compressed_file):
                # 4. 推向 R2
                print(f"🚀 [運輸中] 將轉碼情報推向 R2：{r2_file_name}")
                # 🚀 修正：ContentType 改為音訊通用格式，Bucket 改為變數控制
                s3_client.upload_file(compressed_file, r2_bucket, r2_file_name, ExtraArgs={'ContentType': 'audio/ogg'})
                
                # 5. AI 分析
                print(f"🧠 [AI 行動] 呼叫智囊團執行摘要...")
                analysis, q_score, duration = ai_agent.generate_gold_analysis(compressed_file)

                if analysis:
                    # 6. Telegram 報戰
                    print(f"📡 [情報發布] 正在推送報戰...")
                    date_label = datetime.now().strftime("%m/%d/%y")
                    report_msg = ai_agent.format_mission_report(
                        "Gold", episode_title, audio_url, analysis, date_label, duration, source_name
                    )
                    
                    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
                    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
                    requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage", 
                                   json={"chat_id": tg_chat_id, "text": report_msg, "parse_mode": "Markdown"})

                # 7. 更新資料庫
                supabase.table("mission_queue").update({
                    "status": "completed",
                    "r2_url": r2_file_name,
                    "mission_type": "scout_finished_with_ai_compressed"
                }).eq("id", mission_data['id']).execute()
                print(f"🏆 [任務達成] {episode_title[:15]}... 搬運歸檔完成。")

        except Exception as e:
            print(f"❌ [任務潰敗] 失敗原因：{str(e)}")
        finally:
            # 清理所有本地暫存
            for f in [raw_file, compressed_file]:
                if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    run_transport_and_report()