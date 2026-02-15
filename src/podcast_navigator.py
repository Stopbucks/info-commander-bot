# ---------------------------------------------------------
# 本程式碼為：Podcast_navigator，處理擬態池,TLS, proxy, cookie
# ---------------------------------------------------------

import time
import random
from curl_cffi import requests
# 🚀 引入共通工具與配置 [cite: 2026-02-02]
from podcast_utils import MIMIC_POOL, mask_ip, get_random_mimic_target, get_random_jitter, is_target_sensitive

class NetworkNavigator:
    """
    🛰️ [通訊部隊] 執行者 - v6.1 (穩定重構版)
    職責：管理 Session、身分擬態、執行人類行為雜訊。
    """
    
    def __init__(self, squad_config):
        self.config = squad_config
        self.session = self._init_session()
        print(f"🎭 [身分識別] 小隊: {self.config['squad_name']} | Hash: {self.config['identity_hash']}")

    # 🚀 支援 with 語法的第一動
    def __enter__(self):
        return self

    # 🚀 支援 with 語法的結束動
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

 
    def _init_session(self):
        """🚀 [連線池初始化] 針對 ScraperAPI 採取透明傳輸，其餘維持強擬態 [cite: 2026-02-14]"""
        path_id = self.config.get('path_id') # 獲取目前的傳輸路徑標記。
        
        # 🏹 [智慧分流]：判定是否為 ScraperAPI 路徑以避免雙重擬態衝突 (HTTP 400)
        if path_id == "RE":
            print("💎 [ScraperAPI] 採用標準 HTTP/1.1 透明傳輸協定 (穩定版)。")
            # 🚀 關鍵修正：強制指定 HttpVersion.V1_1，避開代理層的 H2 衝突
            from curl_cffi import requests as cffi_requests
            session = cffi_requests.Session(http_version=cffi_requests.HttpVersion.V1_1)
        else:
            # 🛡️ 標準擬態流程：根據演進引擎發放裝備
            imp = self.config.get('curl_config', {}).get('impersonate', 'chrome110')
            try:
                session = requests.Session(impersonate=imp) # 嘗試發起擬態連線。
            except Exception as e:
                print(f"🚨 [裝備報警] 版本 {imp} 異常，切換至穩定版備援。")
                session = requests.Session(impersonate="chrome110") # 執行備援擬態。

        # 2. 標頭淨化：套用傳入的自定義 Headers (如有)
        session.headers.update(self.config.get('curl_config', {}).get('headers', {})) # 注入配置標頭。

        # 3. 代理配置：確保在 return 之前完成掛載
        proxy_url = self.config.get('transport_proxy') # 讀取目前的代理地址。
        if proxy_url and proxy_url != "GitHub_Runner_Direct":
            session.proxies = {"http": proxy_url, "https": proxy_url} # 執行代理隧道綁定。
        
        # 4. 身分繼承：掛載歷史 Cookies 紀錄
        history_cookies = self.config.get('history_cookies') # 領取雲端同步的身分紀錄。
        if history_cookies:
            session.cookies.update(history_cookies) # 執行身分繼承。
            print(f"📦 [身分繼承] 已掛載身分 {self.config['identity_hash']} 的 Cookies。")

        return session # 確保所有設定完成後才回傳連線池實例。


    def perform_mimicry_pulse(self, mode="light", count=3):
        # 🚀 根據模式決定訪問類別 (輕量用喚醒，重裝用新聞)
        category = "WAKEUP_PINGS" if mode == "light" else "NEWS_STATIONS"
        for i in range(count):
            url = get_random_mimic_target(category)
            try:
                # 💡 使用 verify=False 避免在 GitHub 環境出現 SSL 報錯
                print(f"🎭 [擬態巡航 {i+1}/{count}] 模擬閱讀：{url.split('/')[2]}...")
                self.session.get(url, timeout=10, verify=False)
                # 💡 只有在不是最後一次時執行長等待，避免連續請求特徵
                if i < count - 1: time.sleep(get_random_jitter(120, 200))
            except: pass

    def _perform_mimic_knock(self, target_url, warm_up=False):
        # 🚀 判斷目標是否敏感，優先去敲 Apple 的門
        if is_target_sensitive(target_url):
            selected_url = MIMIC_POOL["APPLE_CORE"][0] if warm_up else random.choice(MIMIC_POOL["APPLE_CORE"])
            prefix = "🔥 [灰色預熱]" if warm_up else "🍎 [擬態優先]"
        else:
            selected_url = get_random_mimic_target("GENERAL_COVER")
            prefix = "📡 [擬態隨機]"

        print(f"{prefix} 目標：{selected_url}")
        try:
            # 💡 根據預熱模式選擇 GET 或 HEAD 請求，並豁免 SSL
            if warm_up:
                self.session.get(selected_url, timeout=10, verify=False)
                time.sleep(get_random_jitter(1.5, 3.0))
            else:
                self.session.head(selected_url, timeout=5, verify=False)
                time.sleep(get_random_jitter(0.5, 1.2))
        except: pass
    

    def run_pre_flight_check(self):
        # 🚀 執行輕量擬態脈衝增加身分權重
        self.perform_mimicry_pulse(mode="light")
        path_id = self.config.get('path_id', 'Unknown')
        print(f"📡 [深度體檢中] 驗證路徑 ID: {path_id}...")
        results = {"status": False, "data": {}}
        
        # 🚀 [策略修正]：若為救援路徑 (RE)，直接放行，避開複雜代理握手導致的超時
        if path_id == "RE":
            print("🚀 [救援路徑] 免除第三方 IP 鑑識，直接出航 (Trust ScraperAPI).")
            return {"status": True, "data": {"ip": "Verified_via_RE", "org": "ScraperAPI_Mesh"}}

        # 🛡️ 標準路徑 (A, B, C, D) 執行嚴格體檢
        try:
            ip_data = {}
            for api in ["http://ip-api.com/json/", "https://ipapi.co/json/"]:
                try:
                    # 💡 體檢連線也加入 verify=False，確保環境不干擾診斷
                    resp = self.session.get(api, timeout=15, verify=False)
                    if resp.status_code == 200:
                        ip_data = resp.json()
                        break
                except: continue

            if ip_data:
                results["data"] = {
                    "ip": ip_data.get("query") or ip_data.get("ip", "?.?.?.?"),
                    "org": ip_data.get("isp") or ip_data.get("org", "Unknown"),
                    "countryCode": ip_data.get("countryCode") or ip_data.get("country_code", "Unknown")
                }
                results["status"] = True
                print(f"✅ [標準體檢成功] 出口 IP: {results['data']['ip']}")
            return results
        except Exception as e:
            print(f"⚠️ [自檢中斷] 異常: {e}")
            return results

 # --統一標頭變數名稱並確保運輸安全----
    def download_podcast(self, url, filename):
        r = None
        try:
            self.perform_mimicry_pulse(mode="heavy")
            self._perform_mimic_knock(url)
            time.sleep(get_random_jitter(0.8, 1.5))
            
            # 🚀 [核心修正]：統一變數名稱為 headers_to_use
            if self.config.get('path_id') == "RE":
                print("💎 [ScraperAPI] 注入基礎導航標頭以優化穿透力。")
                # 💡 為 ScraperAPI 準備最精簡的真實瀏覽器特徵
                headers_to_use = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "*/*",
                    "Connection": "keep-alive"
                }
            else:
                headers_to_use = None # 其餘小隊維持 Session 預設的演進指紋。

            print(f"📡 [發起任務] 目標網址: {url}")
            
            # 🚀 執行 GET 請求，確保使用正確的標頭變數與 SSL 豁免
            r = self.session.get(url, stream=True, timeout=300, 
                                 allow_redirects=True, verify=False,
                                 headers=headers_to_use) # 一行註解：確保使用淨化後的標頭。
            r.raise_for_status()
            
            # 🚀 執行流式寫入
            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
            print(f"✅ 運輸成功：音檔已安全送達 {filename}")
            return True
        except Exception as e:
            print(f"❌ 運輸失敗：{str(e)}")
            return False
        finally:
            if r: r.close() # 確保連線資源釋放。


    # 🔥 [進化戰技] 幽靈取證：403 熔斷與長延遲試探  
    def preflight_warmup(self, target_url):
        """
        🔥 [預熱] 整合 HEAD 探路、中立哨所檢查與幽靈長延遲取證
        """
        host = target_url.split('/')[2]
        print(f"🔍 [預熱-HEAD] 正在對目標發起低頻探路: {host}")
        
        # 💡 紀錄起始時間，用以計算精準的網路延遲 (Latency)
        start_time = time.time()
        
        try:
            # 1. 📡 第一動：發起 HEAD 請求，探查目標伺服器反應 加入 verify=False 繞過憑證錯誤
            resp = self.session.head(target_url, timeout=20, verify=False)
            latency = (time.time() - start_time) * 1000
            
            # 2. 🛡️ 403 熔斷：一旦身分暴露，啟動「幽靈取證」程序
            if resp.status_code == 403:
                print("🛑 [熔斷] 偵測到 403！開始執行「幽靈化」延時取證...")
                
                # A. 🕵️ [偵察] 訪問 Google 崗哨：判定是否為全域 IP 封鎖
                try:
                    sentinel = self.session.get("https://www.google.com/generate_204", timeout=10, verify=False)
                    ip_status = "CLEAN" if sentinel.status_code == 204 else "SUSPICIOUS"
                except: ip_status = "TIMEOUT"
                
                # B. 🕒 [幽靈化延遲]：隨機靜默，燥化機器人連續特徵
                wait_time = get_random_jitter(180, 360) 
                print(f"🕒 [幽靈化] 進入靜默偵查期，預計等待 {wait_time/60:.1f} 分鐘後自動關閉...")
                time.sleep(wait_time)
                
                # C. 🕵️ [偵察] 根目錄敲門：判定封鎖深度
                try:
                    root_url = f"{target_url.split('/')[0]}//{host}/"
                    root_resp = self.session.head(root_url, timeout=10, verify=False)
                    ban_depth = "DOMAIN_LEVEL" if root_resp.status_code == 403 else "RESOURCE_ONLY"
                except: ban_depth = "UNKNOWN"
                
                # 💡 回傳情報包裹，供 Processor 進行閉環存檔
                return {"reason": "403_FORBIDDEN", "ip_reputation": ip_status, "ban_depth": ban_depth}
                

            # 3. 🕒 正常路徑：執行 3 ~ 6 秒的「環境適應延遲」
            interval = get_random_jitter(3.0, 6.0)
            print(f"🕒 [環境適應] 預計停留 {interval:.1f} 秒後發起實戰提取...")
            time.sleep(interval)

            # 4. 🍎 溫養增益：若為溫養模式，執行額外擬態
            if self.config.get('is_warmup'):
                self._perform_mimic_knock(target_url, warm_up=True)
                
            return True # 預熱完畢，准許進入下載環節
            
        except Exception as e:
            print(f"⚠️ [預熱異常] {e}")
            return False
            
 
    def run_rest_warmup(self):
        """🔥 [休息日] 深度溫養計畫：模擬真實人類的新聞閱讀行為"""
        print(f"🎭 [導航員] 啟動國際化人格溫養模式...")
        
        if random.random() > 0.3:
            self.perform_mimicry_pulse(mode="heavy")

        # 🚀 [修正] 擴展名單並加入隨機去重複邏輯，對齊 Processor 的人格模型 [cite: 2026-01-16]
        mimicry_pool = [
            "https://www.apple.com", "https://www.google.com",
            "https://www.bbc.com", "https://www.cnn.com", 
            "https://www.theguardian.com", "https://www.bloomberg.com",
            "https://www.washingtonpost.com", "https://www.reuters.com",
            "https://www.nytimes.com"
        ]
        
        # 使用 random.sample 確保這次溫養的 3 個網站絕不重複 [cite: 2026-01-16]
        targets = random.sample(mimicry_pool, 3)

        for i, url in enumerate(targets, 1):
            print(f"🎭 [溫養 {i}/3] 正在閱讀：{url}")
            # 💡 warm_up=True 會執行較輕量的 HEAD 請求或 robots.txt 探路
#           #🚀 修正點：加上底線 _perform_mimic_knock
            self._perform_mimic_knock(url, warm_up=True)
            time.sleep(get_random_jitter(5, 10))
            
            if i < 3:
                # 模擬人類在不同新聞網手間切換的「換氣時間」 [cite: 2026-02-02]
                time.sleep(get_random_jitter(8.0, 20.0))
# ===========================================================================

    def run_pre_combat_recon(self, target_url="https://podcasts.apple.com/"):
        """💎 [實戰日] 戰前偵察"""
        print(f"📡 [導航員] 執行戰前前哨偵察...")
        self._perform_mimic_knock(target_url, warm_up=False)
        # 🛡️ 這裡保留 3-6 秒思考時間 [cite: 2026-02-02]
        time.sleep(get_random_jitter(3.0, 6.0))


    def save_identity_state(self, current_ip=None, current_org=None):
        """💾 [存檔] 確保身分證包含 IP 與 ISP 資訊"""
        try:
            return {
                "cookies": self.session.cookies.get_dict(),
                "identity_hash": self.config['identity_hash'], # 標籤對齊
                "ip": current_ip or "?.?.?.?",
                "org": current_org or "Unknown",
                "last_active": time.time(),
                "path_id": self.config['path_id']
            }
        except: return None

    def close(self):
        self.session.close()