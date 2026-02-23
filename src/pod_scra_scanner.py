# ---------------------------------------------------------
# 本程式碼：src/pod_scra_scanner.py v1.7 (資源看板版)
# 任務：統一破防掃描器，標註點數配額與隱身策略
# 提醒：Zenrows 3/3日棄用，SCRAPERAPI申請帳號補點
# ---------------------------------------------------------
import requests, urllib.parse, random

def fetch_html(provider_key, target_url, keys):
    TO = 60 # 統一 60 秒超時，應對渲染場景
    
    # 支援多組 API Key：處理 ScraperAPI 等多帳號輪詢
    current_key = keys.get(provider_key)
    if isinstance(current_key, list) and current_key:
        current_key = random.choice(current_key)

    try:
        # 1. 主力部隊：SCRAPERAPI (1,000 點/月，萬用消耗品)
        if provider_key == "SCRAPERAPI":
            # 🎯 開啟 render=true。雖然點數消耗較快，但能穿透動態網址。
            params = {'api_key': current_key, 'url': target_url, 'render': 'true'}
            return requests.get('https://api.scraperapi.com', params=params, timeout=TO)

        # 2. 臨終部隊：ZENROWS (試用期將屆，僅供緊急調度)
        elif provider_key == "ZENROWS":
            # 🎯 搭配 js_render 與 premium_proxy，做為最後的防線。
            params = {'apikey': current_key, 'url': target_url, 'js_render': 'true'}
            return requests.get('https://api.zenrows.com/v1/', params=params, timeout=TO)

        # 3. 轉運專員：WEBSCRAPING (2,000 點/月，性價比之選)
        elif provider_key == "WEBSCRAPING":
            # 🎯 擅長處理轉址。若 Hasdata 告急，此為第一順位接替者。
            params = {'api_key': current_key, 'url': target_url, 'js': 'true'}
            return requests.get('https://api.webscraping.ai/html', params=params, timeout=TO)

        # 4. 備援破城槌：SCRAPEDO (1,000 點/月，簡單暴力)
        elif provider_key == "SCRAPEDO":
            # 🎯 採用 URL 直接拼接模式，反應速度快，適合小批次衝鋒。
            encoded_url = urllib.parse.quote(target_url)
            api_url = f"https://api.scrape.do?token={current_key}&url={encoded_url}&render=true"
            return requests.get(api_url, timeout=TO)

        # 5. 特種部隊：HASDATA (每日 100 點，住宅代理火力加強版)
        elif provider_key == "HASDATA":
            # 🎯 將 proxy_type 由 datacenter 提升至 residential。
            # 「住宅代理」隱身斗篷，以最高穿透力應對 Podbay 的最終封鎖。
            headers = {'x-api-key': current_key}
            params = {'url': target_url, 'js_render': 'true', 'proxy_type': 'residential'}
            return requests.get('https://api.hasdata.com/scrape', headers=headers, params=params, timeout=TO)

        # 6. 通用全能：ScrapingAnt (1,000 點/月，穩定 JS 渲染步兵，每月23日renew )
        elif provider_key == "SCRAPINGANT":
            # 🎯 擅長一般 JS 動態頁面，適合處理 Podbay 的內容提取。
            encoded_url = urllib.parse.quote(target_url)
            api_url = f"https://api.scrapingant.com/v2/general?url={encoded_url}&x-api-key={current_key}&browser=true"
            return requests.get(api_url, timeout=TO)
        
        return None
    
    except Exception as e:
        print(f"⚠️ [Scanner 異常] {provider_key} 偵察機失聯: {e}")
        return None