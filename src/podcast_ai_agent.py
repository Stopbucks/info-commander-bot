# ---------------------------------------------------------
# 本程式碼為：Podcast_ai_agent，負責提示詞給予gemini-2.5(模型勿動)判斷+報告
# ---------------------------------------------------------
import google.generativeai as genai
import os
import re
import time
from podcast_prompts import GEMINI_MAIN_PROMPT, WEEKLY_STRATEGIC_PROMPT, SIMPLE_FALLBACK_PROMPT
from groq import Groq

class AIAgent:
    """
    🧠 [智囊團] 職責：執行核心 Prompt、生成高品質情報、維持格式一致性。
    """
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        # 🚀 升級為二代大腦 2.5 版本
        self.model = genai.GenerativeModel("gemini-2.5-flash")
# --- [更新處：新增 Groq 配置] ---
        self.groq_key = os.environ.get("GROQ_API_KEY")
        self.groq_client = Groq(api_key=self.groq_key) if self.groq_key else None

    # ---------------------------------------------------------
    # ⚔️ 游擊隊專用：Groq + Opus 極速摘要流程 [cite: 2026-01-16]
    # ---------------------------------------------------------
    def generate_groq_summary(self, opus_file_path):
        """🚀 [g-小隊] 使用 Groq 執行轉寫與摘要，徹底避開 GCP 流量 [cite: 2026-01-16]"""
        if not self.groq_client:
            print("❌ [Groq 故障] 未偵測到 GROQ_API_KEY。")
            return None

        try:
            print(f"🧬 [Groq 啟動] 正在解析 Opus 音檔：{os.path.basename(opus_file_path)}")
            
            # Step 1: 語音轉文字 (使用 Whisper-large-v3 模型) [cite: 2026-01-16]
            with open(opus_file_path, "rb") as file:
                transcription = self.groq_client.audio.transcriptions.create(
                    file=(opus_file_path, file.read()),
                    model="whisper-large-v3",
                    response_format="text",
                    language="en"  # 強制英文識別以提高演講準確度
                )

            # Step 2: 呼叫"llama-3.1-70b-versatile",摘要分析，引用 SIMPLE_FALLBACK_PROMPT 
            print(f"📝 [摘要中] 正在發起 Groq 輕量化策展...")
            completion = self.groq_client.chat.completions.create(
                
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SIMPLE_FALLBACK_PROMPT},
                    {"role": "user", "content": f"請分析以下 Podcast 逐字稿內容：\n\n{transcription}"}
                ],
                temperature=0.5,
                max_tokens=1024
            )
            
            return completion.choices[0].message.content

        except Exception as e:
            print(f"❌ [Groq 崩潰] 執行異常：{str(e)}")
            return f"⚠️ 摘要失敗，請檢查 Groq 額度或連線狀況。錯誤細節：{str(e)}"
        

    def generate_gold_analysis(self, audio_file_path):
        """執行深度 AI 分析，具備超時防禦、強制清理與戰術追蹤列印 [cite: 2026-02-01]"""
        start_time = time.time()
        uploaded_file = None
        
        print(f"🧠 [AI任務] 開始分析目標音檔：{os.path.basename(audio_file_path)}")
        
        try:
            # 1. 衛星上傳
            print(f"🛰️ [1/4] 正在將音檔投送至 Google 臨時空間...")
            uploaded_file = genai.upload_file(audio_file_path, mime_type="audio/mpeg")
            
            # 2. 狀態監控
            retries = 30
            print(f"⏳ [2/4] 等待雲端轉碼與環境就緒 (預計 30-150 秒)...")
            while uploaded_file.state.name == "PROCESSING" and retries > 0:
                if retries % 6 == 0:  # 每隔 30 秒印一次狀態，避免洗版
                    print(f"   ... 衛星回報：處理中 (剩餘嘗試次數: {retries})")
                time.sleep(5)
                uploaded_file = genai.get_file(uploaded_file.name)
                retries -= 1
            
            if retries <= 0:
                print("❌ [2/4 故障] 衛星超時！Google 伺服器處理過久，啟動防禦性熔斷。")
                return None, 0, 0
            
            print(f"✅ [2/4] 環境就緒，音檔已解鎖。")

            # 3. 核心推理
            print(f"🧬 [3/4] 智囊團啟動：正在發起 Gemini 深度策展分析...")
            response = self.model.generate_content([GEMINI_MAIN_PROMPT, uploaded_file])
            final_text = response.text
            
            # 4. 數據提取
            score_match = re.search(r"綜合情報分.*?(\d+)", final_text)
            q_score = int(score_match.group(1)) if score_match else 20
            
            duration_mins = max(1, round((time.time() - start_time) / 60))
            print(f"🏆 [4/4] 分析成功！情報評分：{q_score} | 總耗時：{duration_mins} 分鐘")
            
            return final_text, q_score, duration_mins
            
        except Exception as e:
            print(f"❌ [AI崩潰] 執行期間遭遇攔截或異常：\n   └─ 錯誤細節: {str(e)}")
            return None, 0, 0
            
        finally:
            # 5. 強制資源回收
            if uploaded_file:
                try:
                    uploaded_file.delete()
                    print("🧹 [清理] 雲端臨時資源已安全回收。")
                except Exception as cleanup_err:
                    print(f"⚠️ [警告] 資源釋放受阻：{cleanup_err}")
    
    # ==========================================================================
    # --- 📋 戰略報告系統 (單篇報告、週戰略報、月度情報報) ---
    # ==========================================================================

    def format_mission_report(self, tier, title, link, content, date_label, duration, podcast_name, audio_duration="未知"):
        """🚀 [格式化] 更新以支援游擊隊標籤與 Opus 說明 [cite: 2026-01-16]"""
        
        # 🚀 修改處：新增 Guerrilla 標頭
        headers = {
            "Gold": "🏆 黃金等級-深度策展情報", 
            "Platinum": "💿 白金等級-節目簡訊",
            "Guerrilla": "📡 g-小隊-游擊情報" 
        }
        header = f"{headers.get(tier, 'ℹ️ 情報通知')} ({date_label})"

        # 🚀 修改處：更新決策筆記，加入游擊戰模式說明 [cite: 2026-01-16]
        DECISION_NOTE = (
            "--- 📊 Info Commander 決策筆記 ---\n"
            "📡 游擊戰模式：採用 Opus 壓縮與 Groq 摘要，節省 90% 傳輸成本。\n"
            "💎 模式翻轉：音檔 > 15MB 啟動保底抽檢。"
        )

        return (
            f"{header}\n\n🎙️ 頻道：{podcast_name}\n📌 標題：{title}\n\n{content}\n\n"
            f"🔗 收聽：{link}\n⏳ 長度：{audio_duration}\n"
            f"> AI 處理耗時 {duration} 分鐘\n\n{DECISION_NOTE}"
        )

    def generate_weekly_strategic_report(self, monitor_summary):
        """🧠 [戰略升級] 呼叫 Gemini 進行一週深度除錯與業界校準分析 [cite: 2026-02-03]"""
        # 🚀 引入移至 prompts.py 的週報專屬提示詞
        from podcast_prompts import WEEKLY_STRATEGIC_PROMPT
        
        try:
            # 💡 第一段：加入戰略指揮部標頭
            header = "🛡️ **Info Commander 週戰略戰報**\n"
            header += "📍 本週戰場數據與質化深度取證如下：\n"
            header += "--------------------------------\n"
            
            # 💡 第二段：調用 Gemini 執行除錯靈魂的深度分析
            response = self.model.generate_content([WEEKLY_STRATEGIC_PROMPT, monitor_summary])
            
            return f"{header}\n{response.text}\n\n💡 指令：若偵察成功率低於 80%，建議檢查代理 IP 信用分。"
        except Exception as e:
            return f"❌ [大腦過載] 無法生成週報，錯誤細節: {str(e)}"

    def generate_monthly_strategic_report(self, consolidated_data):
        """🧠 [戰略分析] 質量並重：針對四週數據進行趨勢分析與改善優化 [cite: 2026-02-03]"""
        # 🚀 此處預留給未來 V7.1 的 MONTHLY_STRATEGIC_PROMPT
        prompt = f"""
        你現在是 Info Commander 小隊的高級戰略分析官。
        請根據過去四週的採集數據進行「質、量並重」的月度總結。
        
        【分析要求】：
        🚫 嚴禁 Markdown 表格。✅ 使用條列式分析。
        🕵️ 深度探討 403 攔截原因與灰色作戰（預熱）的具體成效。
        
        【原始數據包】：
        {consolidated_data}
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"❌ [大腦過載] 無法生成月報: {str(e)}"