
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_transport.py v0.6(AI 戰報整合版)
# 任務：全量下載 -> 串流上傳至 R2 (pod-scra-vault)
# 流程：領命 -> 下載 -> 推 R2 -> 呼叫 AIAgent (Gemini) -> 發送 TG 戰報
# ---------------------------------------------------------

import os, requests, time, random, boto3, io
from supabase import create_client, Client
from datetime import datetime
from pod_scra_ai_agent import AIAgent  # 🚀 引入智囊團模組

def run_transport_and_report():
    # 1. 讀取補給金鑰
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_KEY")
    r2_id = os.environ.get("R2_ACCESS_KEY_ID")
    r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    r2_account_id = os.environ.get("R2_ACCOUNT_ID")
    
    if not all([sb_url, sb_key, r2_id, r2_secret, r2_account_id]):
        print("❌ [資安警報] 環境變數不齊全。")
        return

    # 初始化組件
    supabase: Client = create_client(sb_url, sb_key)
    ai_agent = AIAgent()  # 💡 實例化智囊團
    s3_client = boto3.client(
        's3',
        endpoint_url=f'https://{r2_account_id}.r2.cloudflarestorage.com',
        aws_access_key_id=r2_id,
        aws_secret_access_key=r2_secret,
        region_name='auto'
    )

    # 2. 領取任務 (維持 limit 1 以確保單發精準度)
    missions = supabase.table("mission_queue").select("*") \
        .eq("scrape_status", "success") \
        .eq("status", "pending") \
        .limit(1) \
        .execute()
    
    if not missions.data:
        print("☕ [待命] 倉庫暫無待搬運物資。")
        return

    mission = missions.data[0]
    audio_url = mission.get('audio_url')
    source_name = mission.get('source_name', 'unknown')
    episode_title = mission.get('episode_title', 'Untitled')
    # 一行註解：建立實體暫存檔名，供 AI 讀取。
    local_file = "temp_scout.mp3"
    r2_file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source_name}.mp3"

    print(f"📡 [實戰摘要任務]：{source_name}")

    try:
        # 3. 下載至 GitHub Runner 本機 (為了讓 AI 讀取)
        print(f"📥 [下載中] 正在下載音檔至本機暫存...")
        resp = requests.get(audio_url, timeout=300)
        
        if resp.status_code == 200:
            with open(local_file, "wb") as f:
                f.write(resp.content)
            print(f"✅ [下載完成] 檔案已存於：{local_file}")

            # 4. 上傳至 R2
            print(f"🚀 [運輸中] 正在將檔案推向 R2...")
            s3_client.upload_file(local_file, 'pod-scra-vault', r2_file_name, ExtraArgs={'ContentType': 'audio/mpeg'})
            
            # 5. 🚀 核心：發起 AI 摘要行動
            print(f"🧠 [AI 行動] 呼叫智囊團進行深度解碼摘要...")
            # 一行註解：調用 AIAgent 的黃金等級分析流程。
            analysis, q_score, duration = ai_agent.generate_gold_analysis(local_file)

            if analysis:
                # 6. 格式化戰報並發送 Telegram
                date_label = datetime.now().strftime("%m/%d/%y")
                # 一行註解：透過 AI Agent 格式化戰報。
                report_msg = ai_agent.format_mission_report(
                    "Gold", episode_title, audio_url, analysis, date_label, duration, source_name
                )
                
                # 指揮官，我在此借用您第一管道 processor 的 Telegram 通訊邏輯
                # 為了簡單，我們先在 AI Agent 加一個通訊發送函數
                print(f"📡 [情報發布] 正在推送摘要至 TG 頻道...")
                # (備註：請確認您 AIAgent 有 send_report 邏輯，或在此加入 requests.post)
                # --- 暫代通訊邏輯 ---
                tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
                tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
                requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage", 
                              json={"chat_id": tg_chat_id, "text": report_msg, "parse_mode": "Markdown"})

            # 7. 更新資料庫
            supabase.table("mission_queue").update({
                "status": "completed",
                "r2_url": r2_file_name,
                "mission_type": "scout_finished_with_ai"
            }).eq("id", mission['id']).execute()
            
            print(f"🏆 [任務圓滿成功] 檔案與戰報已結案。")

    except Exception as e:
        print(f"❌ [任務潰敗]：{str(e)}")
    finally:
        # 一行註解：戰場清理，刪除本機 MP3 暫存。
        if os.path.exists(local_file): os.remove(local_file)

if __name__ == "__main__":
    run_transport_and_report()