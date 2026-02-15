# ---------------------------------------------------------
# 本程式碼為：Podcast_Proxy_medic.py，處理 PROXY 問題
# ---------------------------------------------------------
import os
import time
import random  # 🛡️ 確保軍需官能隨機挑選隊員 
import requests 

# --- [測試用:插入此段內容] ---
import urllib3
# 🚀 診斷專用：關閉 verify=False 產生的不安全連線警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# ---------------------------------------------------------
# 1. 代理伺服器清單讀取邏輯 (全專案對齊優化版)
# ---------------------------------------------------------

def load_all_proxies():
    """彙整所有環境變數來源，並執行多行拆解與清洗"""
    vps_raw = os.getenv('VPS_PROXY_URL', '')
    list_raw = os.getenv('PROXY_LIST', '')
    
    gcp_user = os.getenv('GCP_PROXY_USER')
    gcp_pass = os.getenv('GCP_PROXY_PASS')
    gcp_host = os.getenv('GCP_PROXY_HOST')
    gcp_port = os.getenv('GCP_PROXY_PORT')
    gcp_proxy = f"socks5h://{gcp_user}:{gcp_pass}@{gcp_host}:{gcp_port}" if all([gcp_user, gcp_pass, gcp_host, gcp_port]) else ""

    combined_raw = f"{vps_raw}\n{list_raw}\n{gcp_proxy}"
    
    # 💡 修正 1：保留 socks5h 的隊員
    cleaned_proxies = [
        line.strip() 
        for line in combined_raw.splitlines() 
        if line.strip() and "socks5h" in line
    ]

    # 🚀 修正 2 [插入點]：正式讀取 ScraperAPI 並匯入清單
    scrapi_key = os.getenv('SCRAP_API_KEY')
    if scrapi_key:
        # ScraperAPI 使用 http 協定，因此不能放在上面的 socks5h 過濾器中
        scrapi_url = f"http://scraperapi:{scrapi_key}@proxy-server.scraperapi.com:8001"
        cleaned_proxies.append(scrapi_url)
        print(f"📡 [軍醫] 已掛載 ScraperAPI 診斷路徑。")
    
    return cleaned_proxies
# ==============================================================================

# ---------------------------------------------------------
# 2. 設定體檢目標與類別介面
# ---------------------------------------------------------
TARGET_DOMAINS = {
    "Google (基準測試)": "https://www.google.com",
    "WSJ 追蹤器 (pdst.fm)": "https://pdst.fm",
    "Megaphone (swap.fm)": "https://tracking.swap.fm",
    "Acast 伺服器": "https://access.acast.com"
}

class ProxyMedic:
    """🛡️ 軍需官：負責代理池的整合、清洗與供應 [cite: 2026-02-02]"""
    
    @staticmethod
    def get_all_proxies():
        """獲取目前環境中所有可用的代理清單"""
        return load_all_proxies()

    @staticmethod
    def get_random_proxy():
        """為指揮官提供一個隨機隊員 (SOCKS5h) [cite: 2026-02-02]"""
        proxies = load_all_proxies()
        return random.choice(proxies) if proxies else "GitHub_Runner_Direct"

def check_health():
    """執行全方位健檢 [cite: 2026-02-02]"""
    proxies_to_check = load_all_proxies()
    if not proxies_to_check:
        print("⚠️ 無有效代理可供檢測。")
        return

    print(f"🚀 開始對 {len(proxies_to_check)} 組代理路徑進行全方位健檢...\n")
    
    for proxy in proxies_to_check:
        # 💡 一行註解：僅顯示 IP 的最後一段，防止透過日誌回溯您的 VPS 位置 [cite: 2026-02-15]。
        masked_display = f"...{proxy.split('.')[-1] if '.' in proxy else 'Hidden_Node'}"
        print(f"--- 📡 正在檢測隊員：[{masked_display}] ---")
        
        test_proxies = {"http": proxy, "https": proxy}
        for name, url in TARGET_DOMAINS.items():
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'}
                start = time.time()
                # --- [替換為以下具備「強韌診斷」能力的區塊] ---                          
                # 💡 關鍵變動：timeout 延長至 30s，並加入 verify=False
                resp = requests.get(
                    url, 
                    proxies=test_proxies, 
                    timeout=30, 
                    headers=headers,
                    verify=False 
                )
                
                latency = int((time.time() - start) * 1000)
                
                if resp.status_code == 200:
                    print(f"  ✅ {name.ljust(18)} : 200 (OK) | {latency}ms")
                else:
                    print(f"  ⚠️ {name.ljust(18)} : {resp.status_code}")
            except Exception as e:
                print(f"  ❌ {name.ljust(18)} : 失敗 ({str(e)[:20]}...)")
        print("\n")

if __name__ == "__main__":
    check_health()