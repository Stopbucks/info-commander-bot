# ---------------------------------------------------------
# 本程式碼：src/pod_scra_scanner.py v2.0 (全武裝版本)
# 任務：統一破防掃描器，根據供應商自動對位「最強參數」
# ---------------------------------------------------------
import requests, urllib.parse, random

def fetch_html(provider_key, target_url, keys):
    TO = 90 # 90秒超時，應對渲染與高級代理的延遲
    
    current_key = keys.get(provider_key)
    if isinstance(current_key, list) and current_key:
        current_key = random.choice(current_key)
    if not current_key: return None

    try:
        # 1. SCRAPERAPI (主力部隊：強制開啟渲染與高級代理)
        if provider_key == "SCRAPERAPI":
            params = {
                'api_key': current_key, 
                'url': target_url, 
                'render': 'true',     # 🚀 強制渲染
                'premium': 'true'     # 💎 強制高級/住宅代理
            }
            return requests.get('https://api.scraperapi.com', params=params, timeout=TO)

        # 2. WEBSCRAPING (轉運專員：強化轉址處理)
        elif provider_key == "WEBSCRAPING":
            params = {'api_key': current_key, 'url': target_url, 'js': 'true', 'proxy': 'residential'}
            return requests.get('https://api.webscraping.ai/html', params=params, timeout=TO)

        # 3. SCRAPEDO (備援破城槌：快速渲染衝鋒)
        elif provider_key == "SCRAPEDO":
            encoded_url = urllib.parse.quote(target_url)
            api_url = f"https://api.scrape.do?token={current_key}&url={encoded_url}&render=true"
            return requests.get(api_url, timeout=TO)

        # 4. HASDATA (特種部隊：最強住宅代理)
        elif provider_key == "HASDATA":
            headers = {'x-api-key': current_key}
            params = {'url': target_url, 'js_render': 'true', 'proxy_type': 'residential'}
            return requests.get('https://api.hasdata.com/scrape', headers=headers, params=params, timeout=TO)

        # 5. SCRAPINGANT (通用步兵：穩定渲染)
        elif provider_key == "SCRAPINGANT":
            encoded_url = urllib.parse.quote(target_url)
            api_url = f"https://api.scrapingant.com/v2/general?url={encoded_url}&x-api-key={current_key}&browser=true"
            return requests.get(api_url, timeout=TO)
        
        return None
    except Exception as e:
        print(f"⚠️ [Scanner 異常] {provider_key} 失聯: {e}")
        return None