import os # 匯入作業系統模組
import sys # 匯入系統參數模組
import time # 匯入時間模組

# 🚀 [定位線] 注入 src 搜尋路徑，確保能抓到您的 Navigator
sys.path.append(os.path.join(os.getcwd(), 'src'))
from podcast_navigator import NetworkNavigator # 從自訂模組匯入導航員

# 🎯 鎖定單一最穩目標：Internet Archive (Sherlock Holmes)
target = {
    "name": "Archive_Sherlock", 
    "url": "https://archive.org/download/OTRR_Sherlock_Holmes_Sir_Arthur_Conan_Doyle_Library/Sherlock_Holmes_480321_025_The_Case_of_the_Innocent_Murderess.mp3"
}

# 🛠️ 模擬小隊配置：啟動「RE」降級路徑以測試 ScraperAPI
mock_config = {
    "squad_name": "Scraper_Single_Pilot", # 測試小隊名稱
    "identity_hash": "smoke_test_001", # 測試識別碼
    "path_id": "RE", # 🚀 必須為 RE 才能觸發 HTTP/1.1 與代理池邏輯
    "transport_proxy": f"http://scraperapi:{os.environ.get('SCRAP_API_KEY')}@proxy-server.scraperapi.com:8001", # 構建代理字串
    "curl_config": {"impersonate": "chrome124"} # 模擬最新瀏覽器指紋
}

print(f"🛠️ [環境準備] 開始對 {target['name']} 發起單點測試...")

try:
    # 啟動導航員上下文管理員
    with NetworkNavigator(mock_config) as nav:
        save_path = "test_single_output.mp3" # 設定測試輸出路徑
        
        # 1. 執行預檢 (驗證代理伺服器是否握手成功)
        check = nav.run_pre_flight_check() 
        
        # 2. 執行限額下載演習
        if check.get("status"):
            print(f"📡 運輸通道已開啟: {target['url']}")
            
            # 💡 [戰術優化]：透過 nav.session 執行流式讀取，抓到 1MB 就跑
            # 這樣既能驗證連線成功，又不會耗費過多 ScraperAPI 流量點數
            response = nav.session.get(target['url'], stream=True, timeout=30)
            
            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=1024 * 128): # 每次讀取 128KB
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                        # 🚀 [節能點]：抓滿 1MB 就停止，不再消耗點數
                        if downloaded >= 1024 * 1024: 
                            break
                
                actual_size = os.path.getsize(save_path) / 1024 # 轉換為 KB
                print(f"✅ [測試大捷] 通道暢通！成功取樣：{actual_size:.2f} KB (已手動截斷節省流量)")
            else:
                print(f"❌ [傳輸錯誤] HTTP 狀態碼: {response.status_code}")
        else:
            print("❌ [連線阻塞] 代理伺服器握手失敗，請檢查 SCRAP_API_KEY。")

except Exception as e:
    print(f"💥 [程式崩潰] 錯誤原因: {str(e)}") # 印出崩潰原因

print("\n🏁 測試任務結束。")