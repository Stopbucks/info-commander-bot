# ---------------------------------------------------------
# 本程式碼：src/pod_scra_scanner.py v1.1
# 任務：統一破防掃描器。支援 5 大模式，確保參數對位。
# 註記：ZenRows 申請日 2/18，預計 3/3 棄用檢查。
# ---------------------------------------------------------
import requests, urllib.parse

def fetch_html(provider_key, target_url, keys):
    """
    執行抓取任務。
    provider_key: 模式簡稱 (例如 'ZENROWS')
    keys: 包含所有 API Key 的字典
    """
    try:
        if provider_key == "SCRAPERAPI":
            params = {'api_key': keys['SCRAPERAPI'], 'url': target_url, 'render': 'true'}
            return requests.get('https://api.scraperapi.com', params=params, timeout=60)
            
        elif provider_key == "ZENROWS":
            # 💡 戰報：目前主戰力，試用至 3/3。
            params = {'api_key': keys['ZENROWS'], 'url': target_url, 'js_render': 'true'}
            return requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
            
        elif provider_key == "WEBSCRAPING":
            # 💡 戰報：日後模式二優先，每月 2,000 點
            params = {'api_key': keys['WEBSCRAP'], 'url': target_url, 'js': 'true', 'proxy': 'datacenter'}
            return requests.get('https://api.webscraping.ai/html', params=params, timeout=60)
            
        elif provider_key == "SCRAPEDO":
            # 💡 戰報：備援破城槌，每月 1,000 點
            encoded_url = urllib.parse.quote(target_url)
            api_url = f"https://api.scrape.do?token={keys['SCRAPEDO']}&url={encoded_url}&render=true"
            return requests.get(api_url, timeout=60)

            #---  增加 HasData 採用 Header 帶入 Key，每次成功抓取需 10 點。 ---#
        elif provider_key == "HASDATA":
            # 💡 戰報：備援破城槌，每日 100 點
            headers = {'x-api-key': keys['HASDATA']}
            params = {
                'url': target_url,
                'js_render': 'true',      # 必開，以應對 Podbay
                'proxy_type': 'datacenter' # 使用 DC 代理以節省點數
            }
            return requests.get('https://api.hasdata.com/scrape', headers=headers, params=params, timeout=60)
# -----(定位線)以上修改----
        return None
    except Exception as e:
        print(f"⚠️ [Scanner 異常] {provider_key} 連線失敗: {e}")
        return None