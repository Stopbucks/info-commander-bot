import os
import time
from groq import Groq

# ==========================================
# 🔑 1. 初始化區塊
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ==========================================
# 🚀 2. 核心備援函式 (智慧分段加強版)
# ==========================================
def run_fallback(file_path, system_prompt):
    """
    執行備援路徑：音檔轉錄 -> 智慧分段分析 -> 合併產出。
    解決 Groq 免費版 6,000 TPM 限制，並透過 100 秒冷卻確保穩定性。
    """
    if not client:
        print("❌ [groq_fallback] 錯誤：未設定 GROQ_API_KEY。")
        return None

    try:
        # --- Step 1: 🎙️ 執行 Whisper 轉錄 ---
        print("⚡ [groq_fallback] 啟動 Whisper 轉錄...")
        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(file_path, file.read()),
                model="whisper-large-v3",
                response_format="text",
                language="en"
            )
        
        # --- Step 2: 🧠 智慧分段分析與強化冷卻 ---
        # 說明：針對 6,000 TPM 限制，每段切割為 7000 字元 (約 4500 tokens)
        print(f"📝 轉錄完成 ({len(transcription)} 字)，啟動分段冷卻分析...")
        
        chunk_size = 7000 
        chunks = [transcription[i:i + chunk_size] for i in range(0, len(transcription), chunk_size)]
        partial_results = []

        for index, chunk in enumerate(chunks):
            part_no = index + 1
            print(f"⏳ 正在分析第 {part_no}/{len(chunks)} 段...")

            # 🚀 植入引導 Prompt：告知 AI 這是切割檔案且需視為一體
            chunk_prompt = (
                f"【注意：這是長逐字稿的第 {part_no} 部分，請視為同一個檔案處理。】\n\n"
                f"請依據先前指示的格式進行分析：\n\n{chunk}"
            )

            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": chunk_prompt}
                ],
                temperature=0.5,
                max_tokens=2048
            )
            
            partial_results.append(completion.choices[0].message.content)

            # 💤 🚀 [強化冷卻] 處理完一段後若還有下一段，強制休息 100 秒以刷新 TPM 配額
            if part_no < len(chunks):
                print(f"💤 為了規避 TPM 限制，強制冷卻 100 秒以準備處理下一段...")
                time.sleep(100)

        # 合併所有段落的分析成果
        final_report = "\n\n=== (下續分段情報) ===\n\n".join(partial_results)
        return final_report

    except Exception as e:
        print(f"⚠️ [groq_fallback] 執行失敗: {str(e)}")
        return None