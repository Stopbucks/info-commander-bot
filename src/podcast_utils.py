# ---------------------------------------------------------
# 本程式碼為：podcast_utils，儲存共通配置與格式化工具 [cite: 2026-02-14]
# 基準校準塔：https://developer.chrome.com/release-notes?hl=zh-tw
# ---------------------------------------------------------
import random
import time
from datetime import datetime, timezone

# 🎯 擬態敲門目標池
MIMIC_POOL = {
    "APPLE_CORE": ["https://podcasts.apple.com/", "https://www.apple.com/robots.txt"],
    "GENERAL_COVER": [
        "https://duckduckgo.com/robots.txt", 
        "https://api.github.com/zen", 
        "https://www.google.com/robots.txt"
    ],
    "NEWS_STATIONS": [
        "https://www.bbc.com", 
        "https://www.cnn.com", 
        "https://www.theguardian.com/international"
    ],
    "WAKEUP_PINGS": [
        "https://www.apple.com/library/test/success.html", 
        "https://www.google.com/generate_204"
    ]
}


# =========================================================
# 🚀 數位人格演進引擎 [2026-02-14 最終離散校準版]
# =========================================================
def get_evolved_persona(squad_tag):
    """🚀 [版本指揮官] 根據月度演進尋找 curl_cffi 支援的最近裝備 [cite: 2026-02-14]"""
    now = datetime.now(timezone.utc)
    # 1. 計算自 2026/02 以來經過的總月數
    months_passed = (now.year - 2026) * 12 + (now.month - 2)
    
    # 2. 定義 curl_cffi 目前官方穩定支援的 Chrome 指紋清單
    # 排除掉 125-130 之間的空檔，杜絕 supported 錯誤 [cite: 2026-02-14]
    SUPPORTED_CHROME = [110, 116, 119, 120, 124, 131, 136]

    # 3. 計算目標虛擬版本 (Target Virtual Version)
    if squad_tag == "RE":
        # 🏹 ScraperAPI：基準 119，每月前進 2 個版本
        target_v = 119 + (months_passed * 2)
    elif squad_tag == "GCP":
        return "chrome124" # 🛡️ GCP 鎖定在最穩節點
    else:
        # 🚀 一般小隊：原有 140 基準與減速器邏輯
        intervals = {"GIT": 6, "LA": 1, "JP": 1}
        offsets = {"GIT": 0, "LA": -10, "GCP": -16, "JP": -20}
        interval = intervals.get(squad_tag, 1)
        evolution_step = months_passed // interval
        target_v = 140 + evolution_step + offsets.get(squad_tag, -10)

    # 💡 核心機制：在支援清單中尋找與 target_v 「最接近」的數字
    # 邏輯：取差值絕對值最小者；若距離相等，取較大的版本 (例如 118 會選 119)
    best_match = min(SUPPORTED_CHROME, key=lambda x: (abs(x - target_v), -x))
    
    return f"chrome{best_match}" # 一行註解：確保裝備 100% 受庫支援且符合演進精神。



# 🛡️ [戰略倉庫] 儲存所有手動校準過的 Legacy 裝備，作為自動化失效時的強韌備援
PERSONA_WAREHOUSE = {
    "FLY_JP_LEGACY": {
        "impersonate": "chrome110",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Sec-Ch-Ua": '"Google Chrome";v="110", "Chromium";v="110", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        }
    },
    "FLY_LA_LEGACY": {
        "impersonate": "chrome124",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Sec-Ch-Ua": '"Google Chrome";v="124", "Chromium";v="124", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Platform": '"Windows"'
        }
    },
    "GCP_IPHONE_LEGACY": {
        "impersonate": "safari15_5",
        "headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
            "Accept-Language": "en-US,en;q=0.9"
        }
    },
    "ULTIMATE_FALLBACK": {
        "impersonate": "chrome110",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        }
    }
}

# 🛡️ 路徑身份清單
PATH_CONFIG = {
    "A": "CacheFly", "B": "Cloudflare", "C": "Datacamp", 
    "RE": "ScraperAPI", "D": "DIRECT", "GIT-RE": "Microsoft", "WBS-RE": "Webshare"
}

# 🛡️ 環境識別關鍵字 
RECON_KEYWORDS = ['apple', 'itunes', 'acast']

# =========================================================
# 🚀 共通工具方法 
# =========================================================
def get_random_jitter(min_sec=1.5, max_sec=4.0):
    # 產生模擬人類行為的隨機延遲時間
    return random.uniform(min_sec, max_sec)

def is_target_sensitive(url: str) -> bool:
    # 判斷目標網址是否屬於核心監控範圍 [cite: 2026-02-02]
    return any(kw in url.lower() for kw in RECON_KEYWORDS)

def mask_ip(ip: str) -> str:
    # 直接回傳完整 IP 以利調試 [cite: 2026-01-16]
    if not ip or ip == "?.?.?.?": return "Unknown"
    return str(ip)

def get_random_mimic_target(category: str) -> str:
    # 根據類別隨機挑選擬態目標
    return random.choice(MIMIC_POOL.get(category, MIMIC_POOL["GENERAL_COVER"]))