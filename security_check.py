import os
import re

# 🎯 定義掃描目標：您在系統中使用的核心變數名稱
SENSITIVE_KEYWORDS = [
    "SCRAP_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", 
    "SUPABASE_KEY", "FLY_API_TOKEN", "CRON_SECRET", "RENDER_SECRET"
]

# 🎯 定義正則表達式：捕捉 "key = 'value'" 或 "key: 'value'" 的模式
# 排除讀取環境變數的寫法 (如 os.environ.get)
HARDCODED_PATTERN = r"(['\"])[a-zA-Z0-9\-_]{20,}\1" # 一行註解：偵測長度超過 20 字元的疑似金鑰字串。

def scan_secrets():
    print("🔍 [安全部隊] 啟動專案深度掃描程序...\n")
    found_issues = 0
    
    # 遍歷專案目錄，排除不需掃描的資料夾
    for root, dirs, files in os.walk("."):
        # 排除 git 紀錄與虛擬環境
        if any(ex in root for ex in [".git", "venv", "__pycache__"]): continue
        
        for file in files:
            if file.endswith((".py", ".json", ".yml", ".yaml", ".env")):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            # 1. 檢查變數名稱後是否直接跟著等號與字串
                            for kw in SENSITIVE_KEYWORDS:
                                if kw in line and ("=" in line or ":" in line) and "os.environ" not in line:
                                    # 進一步確認不是在 .gitignore 裡的檔案
                                    print(f"⚠️  [潛在威脅] 檔案: {file_path} (行 {line_num})")
                                    print(f"    內容: {line.strip()}")
                                    found_issues += 1
                except Exception: continue

    if found_issues == 0:
        print("\n✅ [安全報告] 掃描完畢，未發現明顯的硬編碼金鑰。")
        print("💡 提醒：若您的 Secrets 僅存在於 GitHub 設定頁面，則轉為公開是安全的。")
    else:
        print(f"\n🚨 [警告] 共發現 {found_issues} 處疑似外洩點，請在轉為公開前修正！")

if __name__ == "__main__":
    scan_secrets() # 一行註解：執行專案安全檢查。