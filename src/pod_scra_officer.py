# ---------------------------------------------------------
# 本程式碼：src/pod_scra_officer.py v10.3  (極簡指揮中心版)
# 任務：1. 發號施令 (委派 Scout) 2. 全局連線池管理 3. 戰場垃圾清運
# [v10.3 升級] 1. 架構重構：導入「外觀模式 (Facade)」，將高風險連線與解析邏輯全數剝離至 scout.py。
# [v10.3 升級] 2. 隱蔽性提升：建立全局 Requests Session 連線池，交由 Scout 共用，大幅減少 TCP 握手次數與機器人特徵。
# [戰術調整] 擴編偵察裝備庫 (1~5號)，切換至 2 號裝備，維持 6新+2舊 的排程火力。
# [戰術校準] T1 獨立警報：發生 API 耗盡或型別崩潰時，精準打入 tactics 表的「T1 專屬警報欄位」，絕不干擾 T2 主將運作。
# [黃金沉澱] 維持 T1 延遲與 T2 即時雙軌分流邏輯，核心寫入動作交由斥候部隊執行。
# ---------------------------------------------------------
import os, json, requests
from datetime import datetime, timezone, timedelta 
from supabase import create_client, Client
import pod_scra_scout  # 🚀 引入斥候部隊

ACTIVE_STRATEGY = 2 
STRATEGY_MAP = {
    1: {"provider": "SCRAPERAPI", "label": "Win11_Chrome_Premium", "key_name": "SCRAP_API_KEY_V2"},
    2: {"provider": "WEBSCRAPING", "label": "Win11_Chrome_WebScraping", "key_name": "WEBSCRAPING_API_KEY"},
    3: {"provider": "SCRAPEDO", "label": "Win11_Chrome_ScrapeDo", "key_name": "SCRAPEDO_API_KEY"},
    4: {"provider": "HASDATA", "label": "Win11_Chrome_HasData", "key_name": "HASDATA_API_KEY"},
    5: {"provider": "SCRAPINGANT", "label": "Win11_Chrome_Ant", "key_name": "SCRAPINGANT_API_KEY"}
}

def get_secret(key, default=None):
    v_path = "/etc/secrets/render_secret_vault.json"
    if os.path.exists(v_path):
        with open(v_path, 'r') as f:
            v = json.load(f)
            return v.get("active_credentials", {}).get(key, default)
    return os.environ.get(key, default)

def trigger_global_alarm(sb, error_msg):
    """🚨 [T1 專屬警報] 發生異常時寫入 T1 專屬錯誤欄位"""
    try:
        pod_scra_scout.db_jitter()
        sb.table("pod_scra_tactics").update({
            "last_error_type_troop1": f"[Officer 異常] {str(error_msg)[:200]}"
        }).eq("id", 1).execute()
        print(f"🚨 [戰情通報] 已向中央面板 (T1 區塊) 發送異常警報！")
    except Exception as e:
        print(f"⚠️ [警報發送失敗]: {e}")

def run_scra_officer():
    conf = STRATEGY_MAP.get(ACTIVE_STRATEGY)
    provider, persona_label, api_key = conf["provider"], conf["label"], get_secret(conf["key_name"])
    sb: Client = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
    now = datetime.now(timezone.utc)
    
    print(f"🚀 [指揮中心 v10.3] 啟動黑盒子監測掃描... 目前啟用戰術: {ACTIVE_STRATEGY} ({provider})")

    # 🧹 [自動防呆]
    try:
        sb.table("mission_program_master").update({"is_active": True}).is_("is_active", "null").execute()
    except: pass

    # 🌐 建立全局連線池 (Session Pooling)，大幅減少 TCP 握手次數，提升隱蔽性與速度
    scout_session = requests.Session()
    scout_session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"})

    # 定義警報回呼函數，交給 Scout 使用
    def alarm_cb(msg):
        trigger_global_alarm(sb, msg)

    print("\n📡 [任務一] 委派斥候進行 RSS 智慧巡邏...")
    pod_scra_scout.execute_rss_recon(sb, now, scout_session, alarm_cb)

    print(f"\n🔦 [任務二] 委派斥候進行 HTML 攻堅 ({persona_label})...")
    pod_scra_scout.execute_html_recon(sb, now, scout_session, provider, persona_label, api_key, alarm_cb)

    # 任務結束，關閉連線池
    scout_session.close()

    print("\n🧹 [任務三] 啟動戰場掃除...")
    try:
        seventeen_days_ago = (now - timedelta(days=17)).isoformat()
        pod_scra_scout.db_jitter()
        sb.table("mission_queue").delete().lt("created_at", seventeen_days_ago).execute()
        print("✅ 清理完成：17天前的舊任務紀錄已自資料庫移除。")
    except Exception as e:
        print(f"⚠️ 清理失敗: {e}")

if __name__ == "__main__":
    run_scra_officer()