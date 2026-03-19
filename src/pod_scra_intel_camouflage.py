# ---------------------------------------------------------
# 程式碼：src/pod_scra_intel_camouflage.py (V5.6 基因種子偽裝模組)
# 職責：提供千面人級別的 HTTP Headers，規避反爬蟲雷達。
# 戰術：利用「機甲代號 + 日期」作為種子，動態組合大套件與小套件。
# 機制：極簡化來源設定，精準確保 80% 機率為原生 App (None) 下載。
# ---------------------------------------------------------
import random
from datetime import datetime, timezone

def get_camouflage_headers(worker_id: str) -> dict:
    """
    根據「機甲代號 + 今天日期」決定當天的專屬偽裝套裝。
    保證同一個機甲今天內行為一致，但明天自動換裝，且各機甲絕不撞衫。
    """
    # 建立專屬這台機甲今天的「局部亂數產生器」(不影響全域的隨機行為)
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    tactical_rng = random.Random(f"{worker_id}_{today_str}")

    # ==========================================
    # 🧰 [小套件庫] 彈性配件，隨機抽換
    # ==========================================
    
    # 1. 語言偏好 (美國伺服器常見真實分佈)
    LANGUAGES = [
        "en-US,en;q=0.9",                                      # 純美國英語
        "en-US,en;q=0.9,es-US;q=0.8,es;q=0.7",                 # 英語 + 美國西語
        "en-US,en;q=0.9,zh-TW;q=0.8,zh-CN;q=0.7",              # 英語 + 中文
        "en-GB,en-US;q=0.9,en;q=0.8",                          # 英國/國際英語
    ]
    
    # 2. 來源網站 (Referer) - 簡單且優雅的 80% 機率控制
    # 16 個 None + 4 個真實網站 = 20 個選項。抽中 None 的機率為 16/20 = 80%
    REFERERS = [None] * 16 + [
        "https://www.google.com/",                             # Google 搜尋結果
        "https://podcasts.apple.com/",                         # Apple Podcast 網頁版
        "https://t.co/",                                       # Twitter / X 社群分享連結
        "https://www.bing.com/"                                # Bing 搜尋
    ]

    # 3. 音訊請求標準 Accept
    ACCEPT_AUDIO = "audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5"

    # ==========================================
    # 🛡️ [大套件庫] 核心指紋，必須嚴格保持一致性
    # ==========================================
    PROFILES = [
        # 🎭 套裝 0: Windows Chrome 122
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"'
        },
        # 🎭 套裝 1: macOS Safari 17.3 (Safari 原生沒有 Sec-Ch-Ua)
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        },
        # 🎭 套裝 2: Windows Edge 122
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Microsoft Edge";v="122"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"'
        },
        # 🎭 套裝 3: Windows Firefox 123 (Firefox 有專屬的 Fetch 標籤)
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Sec-Fetch-Dest": "audio",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site"
        },
        # 🎭 套裝 4: macOS Chrome 121
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Sec-Ch-Ua": '"Chromium";v="121", "Not A(Brand";v="99", "Google Chrome";v="121"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"'
        }
    ]

    # ==========================================
    # ⚙️ 開始組裝今天的戰鬥裝備
    # ==========================================
    
    # 1. 抽取大套件 (主體裝甲)
    base_profile = tactical_rng.choice(PROFILES)
    headers = base_profile.copy()
    
    # 2. 裝載小套件 (Accept 與 語言)
    headers["Accept"] = ACCEPT_AUDIO
    headers["Accept-Language"] = tactical_rng.choice(LANGUAGES)
    headers["Connection"] = "keep-alive"
    
    # 3. 裝載來源偽裝 (Referer) -> 80% 機率不會發送
    chosen_referer = tactical_rng.choice(REFERERS)
    if chosen_referer:
        headers["Referer"] = chosen_referer
        
    # 4. 裝載隨機快取行為 (模擬人類偶爾按 F5 刷新)
    if tactical_rng.choice([True, False]):
        headers["Cache-Control"] = "max-age=0"

    return headers