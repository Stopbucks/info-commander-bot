# ---------------------------------------------------------
# 本程式碼：src/pod_scra_scanner.py v1.1
# 任務：統一破防掃描器。支援 5 大模式，確保參數對位。
# 註記：ZenRows 申請日 2/18，預計 3/3 棄用檢查。
# ---------------------------------------------------------
# ---------------------------------------------------------
# 本程式碼：src/pod_scra_scanner.py v1.3 (主力更迭版)
# 任務：Hasdata 火力升級、ScraperAPI 多軌備援、WebScraping 定位修正。
# ---------------------------------------------------------
import requests, urllib.parse

def fetch_html(provider_key, target_url, keys):
    # 一行註解：全域超時設定 60 秒，確保 Render 據點能順利簽收後進行長時間等待。
    TO = 60 
    
    try:
        # 1. 主力部隊：SCRAPERAPI (每月 1,000 點)
        if provider_key == "SCRAPERAPI":
            # 一行註解：開啟 render=true 以強制執行 JS 解析，穿透 Podbay 的動態網址防線。
            params = {'api_key': keys['SCRAPERAPI'], 'url': target_url, 'render': 'true'}
            return requests.get('https://api.scraperapi.com', params=params, timeout=TO)
            
        # 2. 臨終部隊：ZENROWS (試用期將屆，僅供緊急調度)
        elif provider_key == "ZENROWS":
            params = {'apikey': keys['ZENROWS'], 'url': target_url, 'js_render': 'true', 'premium_proxy': 'true'}
            return requests.get('https://api.zenrows.com/v1/', params=params, timeout=TO)

        # 3. 轉運專員：WEBSCRAPING (2,000 點/月，擅長處理轉址與隱藏網址)
        elif provider_key == "WEBSCRAPING":
            # 一行註解：利用其穩定的 JS 渲染能力，負責追蹤並解析 Podbay 內部的隱藏音訊流。
            params = {'api_key': keys['WEBSCRAP'], 'url': target_url, 'js': 'true', 'proxy': 'datacenter'}
            return requests.get('https://api.webscraping.ai/html', params=params, timeout=TO)
            
        # 4. 備援破城槌：SCRAPEDO (1,000 點/月)
        elif provider_key == "SCRAPEDO":
            encoded_url = urllib.parse.quote(target_url)
            api_url = f"https://api.scrape.do?token={keys['SCRAPEDO']}&url={encoded_url}&render=true"
            return requests.get(api_url, timeout=TO)

        # 5. 特種部隊：HASDATA (每日 100 點，住宅代理火力加強版)
        elif provider_key == "HASDATA":
            # 🎯 核心升級：將 proxy_type 由 datacenter 提升至 residential。
            # 一行註解：換裝「住宅代理」隱身斗篷，以最高穿透力應對 Podbay 的最終封鎖。
            headers = {'x-api-key': keys['HASDATA']}
            params = {
                'url': target_url,
                'js_render': 'true',
                'proxy_type': 'residential' # 🚀 提升為住宅代理
            }
            return requests.get('https://api.hasdata.com/scrape', headers=headers, params=params, timeout=TO)

        return None
    
    except Exception as e:
        print(f"⚠️ [Scanner 異常] {provider_key} 偵察機失聯: {e}")
        return None