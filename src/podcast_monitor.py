# ---------------------------------------------------------
# 本程式碼為：Podcast_monitor，處理：出勤判定, 路徑選擇, 偵察脈衝
# Upstash 預留：如換 Redis，改 log_scrapi_success 內容，不需改 Rescuer 下載迴圈。
# remove line 363："ip_masked": current_ip,
# ---------------------------------------------------------

import json
import os
import time
import math
import random  # 🚀 [補檔用] 隨機模組，給予 ID 進行補檔
from podcast_utils import PATH_CONFIG, mask_ip  # 🚀  引入共通工具
from datetime import datetime, timezone, timedelta  # 🚀 時間計算直觀[timedelta]

# --- ⚙️ 系統常數配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MONITOR_FILE = os.path.join(CURRENT_DIR, "podcast_monitor.json")


class MemoryManager:
    
    # --- [增加 filename 參數] ---
    def __init__(self, filename="podcast_monitor.json"):
        """🚀 [軍醫核心] 支援動態記憶檔案切換，實現部隊隔離 [cite: 2026-01-16]"""
        self.file_path = os.path.join(CURRENT_DIR, filename)
        self.data = self._load_data()
        self.lambda_constant = 0.0288  
        self.vault_limit = 8           
# ==============================================================================

    def record_incident_report(self, identity_hash, host, diag_data):
        """🛡️ [取證儲存] 紀錄 403 熔斷時的深度診斷數據 [cite: 2026-02-03]"""
        if "incidents" not in self.data:
            self.data["incidents"] = []
        
        report = {
            "identity_hash": identity_hash,
            "host": host,
            "diagnostics": diag_data,
            "timestamp": time.time(),
            "iso_time": datetime.now(timezone.utc).isoformat()
        }
        
        # 僅保留最近 10 筆取證紀錄，避免檔案過大
        self.data["incidents"] = ([report] + self.data["incidents"])[:10]
        self.save()
        print(f"📊 [監視器] 深度取證數據已封存，供後續分析。")

    #---未來安全稽核獨立區塊：可與(def is_identity_safe)進行統整。---
    #---分割原則歷時cookie(數位人格)、共時性IP(例如同一天地理位置)。---
    def check_and_record_drift(self, path_id, current_country):
        """🛡️ 檢查地理位移並實施熔斷機制 [cite: 2026-02-06]"""
        
        # 🚀 [排除邏輯]：ScraperAPI (RE) 路徑跳過地理位移稽核
        if path_id == "RE":
            return True, "✅ 專業代理路徑 (ScraperAPI)，跳過地理稽核。"
        
        path_key = f"drift_lock_{path_id}"
        now = time.time()
        
        # 1. 初始化路徑紀錄
        if path_key not in self.data:
            self.data[path_key] = {"count": 0, "last_country": current_country, "lock_until": 0}

        record = self.data[path_key]

        # 2. 檢查是否處於熔斷期
        if now < record["lock_until"]:
            return False, f"⚠️ 路徑 {path_id} 處於位移熔斷中，剩餘 {int((record['lock_until']-now)/3600)} 小時。"

        # 3. 檢查時間重置 (3 天後自動歸零)
        if record["count"] > 0 and (now - record.get("last_incident_ts", 0)) > (3 * 24 * 3600):
            print(f"♻️ 路徑 {path_id} 位移紀錄已過期，重置計數。")
            record["count"] = 0

        # 4. 判定嚴重位移 (國家碼不同)
        if record["last_country"] and current_country != record["last_country"]:
            record["count"] += 1
            record["last_incident_ts"] = now
            print(f"🚨 [位移警告] 路徑 {path_id} 偵測到地理變動 ({record['last_country']} -> {current_country})！次數: {record['count']}/3")
            
            if record["count"] >= 3:
                record["lock_until"] = now + (3 * 24 * 3600) # 封禁 3 天
                self.save()
                return False, f"❌ 位移過於嚴重，路徑 {path_id} 強制禁飛 3 天。"
        
        # 更新最後位置並存檔
        record["last_country"] = current_country
        self.save()
        return True, "✅ 地理環境穩定。"

    def record_performance(self, host, latency, is_success):
        """📈 [歷時性分析] 紀錄伺服器效能地圖 (聚合版) 超過 7 天的數據自動簡化"""
        if "performance_map" not in self.data:
            self.data["performance_map"] = {}
            
        hour_key = datetime.now(timezone.utc).strftime("%H") # 00-23
        if host not in self.data["performance_map"]:
            self.data["performance_map"][host] = {}
            
        if hour_key not in self.data["performance_map"][host]:
            self.data["performance_map"][host][hour_key] = {"lat_sum": 0, "count": 0, "ok": 0}
            
        # 更新聚合數據 (節省空間)
        stats = self.data["performance_map"][host][hour_key]
        stats["lat_sum"] += latency
        stats["count"] += 1
        if is_success: stats["ok"] += 1
        
        # 🛡️ 超過 7 天或筆數過多時的自動清理 (Placeholder 邏輯)
        self.save()

    def save(self):
        """🚀 [持久化] 將記憶寫回本地 JSON 檔案"""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"⚠️ 存檔失敗: {e}")


    def add_pending_mission(self, source_name, audio_url, mission_type="failed_retry"):
        """📝 將任務加入派工單，並實施飽和警戒檢查 [cite: 2026-02-04]"""
        # 1. 防止重複掛號
        if any(m["audio_url"] == audio_url for m in self.data["pending_missions"]):
            return False
            
        # 2. 🚀 [飽和警戒線] 確保單一節目待辦任務不超過 2 個
        current_pending = sum(1 for m in self.data["pending_missions"] 
                             if m["source_name"] == source_name and m["status"] == "pending")
        if current_pending >= 2:
            print(f"⚠️ [警戒] {source_name} 待辦任務過多，跳過本次掛號以節省資源。")
            return False
        
        # 🚀 [未來導向命名] 使用日期標籤取代部分隨機數
        date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
        safe_name = source_name.replace(" ", "_").replace("'", "")
        task_id = f"task_{safe_name}_{date_tag}"
        
        new_task = {
            "id": task_id,
            "source_name": source_name,
            "audio_url": audio_url,
            "added_at": time.time(),
            "status": "pending",
            "mission_type": mission_type,  
            "retry_count": 0
        }
        
        self.data["pending_missions"].append(new_task)
        self.save()
        print(f"📌 [派工單] 任務已掛號：{source_name} ({mission_type})")
        return True

    def verify_isp_consistency(self, path_id, current_org):
        """🛡️ 檢查當前 ISP 是否與該路徑歷史紀錄相符 (模糊比對版) """
        last_org = self.data.get("last_recon", {}).get("org", "Unknown")
        if last_org == "Unknown": return True
        
        # 🛡️ 只要主要供應商名稱前 3 位一致，即視為同源 (應對名稱微調)
        return last_org[:3].upper() == current_org[:3].upper()
    

    def clean_expired_missions(self, days=7):
        """🧹 清理超過 7 天且已完成或過期的任務"""
        limit_ts = time.time() - (days * 24 * 3600)
        original_count = len(self.data["pending_missions"])
        
        # 僅保留 7 天內的任務，或狀態為 pending 的重要任務
        self.data["pending_missions"] = [
            m for m in self.data["pending_missions"] 
            if m["added_at"] > limit_ts or m["status"] == "pending"
        ]
        
        if len(self.data["pending_missions"]) < original_count:
            print(f"🧹 [監視器] 已清理 {original_count - len(self.data['pending_missions'])} 筆過期任務。")
            self.save()

    def check_scrapi_heavy_limit(self):
        """🛡️ 實施 ScraperAPI 嚴格限額審核 (2+3+5 原則)"""
        now = time.time()
        # 初始化紀錄
        if "scrapi_history" not in self.data:
            self.data["scrapi_history"] = []
            
        # 清洗 48 小時前的舊紀錄
        self.data["scrapi_history"] = [ts for ts in self.data["scrapi_history"] 
                                       if now - ts < (48 * 3600)]
        
        # 計算 24h 與 48h 成功量
        count_24h = sum(1 for ts in self.data["scrapi_history"] if now - ts < (24 * 3600))
        count_48h = len(self.data["scrapi_history"])
        
        # 判定公式: 24h < 3 且 48h < 5
        is_safe = (count_24h < 3 and count_48h < 5)
        return is_safe, count_24h, count_48h

    def log_scrapi_success(self):
        """📝 當 ScraperAPI 救援成功時，紀錄時間點"""
        if "scrapi_history" not in self.data:
            self.data["scrapi_history"] = []
        self.data["scrapi_history"].append(time.time())
        self.save() # 🚀 確保紀錄立即寫回雲端
        print("📊 [監視器] ScraperAPI 配額已更新（+1 成功紀錄）。")

    # --------- 定位點：紀錄 Github 救援次數使用 ---------
    def log_github_rescue_success(self):
        """📝 當 GitHub 救援成功時，紀錄時間點"""
        if "github_rescue_log" not in self.data:
            self.data["github_rescue_log"] = []
        self.data["github_rescue_log"].append(time.time())
        self.save() # 🚀 立即寫回雲端，同步配額狀態
        print("📊 [監視器] GitHub 救援配額已更新（+1 成功紀錄）。")

    # =========================================================
    # 🧬 [核心模組] 數位人格與指紋匹配 (Persona & Footprint)
    # =========================================================

    def update_identity_vault(self, identity_state):
        """🧬 [存入] 同步數位人格，並管理動態足跡庫（IP 與 Cookies 對接）"""
        target_hash = identity_state.get('identity_hash', 'unknown')
        h = f"id_{target_hash}"
        
        if h not in self.data["domains"]:
            self.data["domains"][h] = {"footprint_vault": [], "failures": []}
            
        target_vault = self.data["domains"][h].get("footprint_vault", [])
        current_ip = identity_state.get("ip")

        new_footprint = {
            "ip": current_ip,
            "masked_ip": current_ip,
            "org": identity_state.get("org"),
            "cookies": identity_state.get("cookies"),
            "timestamp": time.time()
        }

        # 🛡️ 檢查是否已有相同 IP，有的話更新，無則新增至首位
        existing_idx = next((i for i, f in enumerate(target_vault) if f["ip"] == current_ip), None)
        if existing_idx is not None:
            target_vault[existing_idx] = new_footprint
        else:
            target_vault.insert(0, new_footprint)

        # ✂️ 維持動態上限 (目前為 8 筆) [cite: 2026-02-06]
        self.data["domains"][h]["footprint_vault"] = target_vault[:self.vault_limit]
        self.save()

    def match_best_footprint(self, identity_hash, current_ip):
        """🔍 [讀取] 尋找與當前 IP 匹配的歷史紀錄 (數位人格重塑的核心)"""
        h = f"id_{identity_hash}"
        vault = self.data["domains"].get(h, {}).get("footprint_vault", [])
        
        # 💡 精準比對：只有當前的 IP 在歷史紀錄中，才回填對應的 Cookies
        match = next((f for f in vault if f["ip"] == current_ip), None)
        
        if match:
            print(f"🎯 [人格重塑] 發現匹配 IP：{mask_ip(current_ip)}，準備載入專屬 Cookies。")
            return match["cookies"]
        
        return None
    # =========================================================
    # 🕵️ [路徑審計] IP 飄移分析工具 [cite: 2026-02-03]
    # =========================================================

    def get_last_known_ip(self, path_id):
        """🔍 取得該路徑上一次成功偵察的 IP"""
        history = self.data.get("path_history", {}).get(str(path_id), [])
        return history[0] if history else None # 返回最新的紀錄

    def count_unique_ips(self, path_id, current_ip):
        """📊 統計該路徑出現過多少種不同的出口 IP"""
        if "path_history" not in self.data: self.data["path_history"] = {}
        pid_str = str(path_id)
        
        if pid_str not in self.data["path_history"]:
            self.data["path_history"][pid_str] = []
            
        history = self.data["path_history"][pid_str]
        
        # 💡 若當前 IP 不在歷史中，則加入歷史清單 (去重統計)
        if current_ip not in history:
            history.insert(0, current_ip) # 置頂最新 IP
            # 限制歷史長度為 20 筆，避免紀錄過多
            self.data["path_history"][pid_str] = history[:20]
            
        return len(set(history)) # 返回獨特 IP 的總數

    def reload(self):
        """🚀 當 GCP 下載完最新記憶後，強制重載數據至記憶體"""
        self.data = self._load_data()
        print("🧠 [記憶重載] 已同步最新的雲端數位指紋紀錄。")

    def _load_data(self):
        """🚀 具備版本自動升級能力的數據讀取邏輯"""
        raw_data = {
            "last_recon": {},
            "domains": {},
            "burned_identities": {},
            "github_rescue_log": [],  # 🚀 專門存放 GitHub 成功救援的時間戳
            "scrapi_history": [],     # 存scrapi確保這兩個欄位在 raw_data 頂層
            "global_failures": [],
            "server_stats": {},
            "incidents": [],
            "path_history": {},
            
            "pending_missions": [],   # 🚀 [紀錄] 待補檔任務清單 ，下方點數計算
            "scrap_api_vault": {
                "current_balance": 1000.0,
                "weekly_carry_over": 0.0,
                "last_refill_date": datetime.now(timezone.utc).strftime("%Y-%m-%d")
            }
        }
        
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                    # 💡 關鍵：將本地存檔與預設結構進行「深度合併」，確保舊資料不丟失、新欄位不遺漏
                    raw_data.update(stored)
                    return raw_data
            except Exception as e:
                print(f"⚠️ 讀取檔案失敗，使用預設結構: {e}")
        
        return raw_data
        
    # 🚀 [ISP]：一致性校對
    def verify_isp_consistency(self, path_id, current_org):
        """🛡️ 檢查當前 ISP 是否與該路徑歷史紀錄相符"""
        last_org = self.data.get("last_recon", {}).get("org", "Unknown")
        if last_org == "Unknown": return True
        
        return last_org[:3].upper() == current_org[:3].upper() # 供應商名（前三字）相同，就通過
   
    # ==========================================================================
    # --- 🛰️ 1. 偵察脈衝紀錄邏輯 (路徑審計與 ISP 校對) ---
    # ==========================================================================

        # --- 雙重驗證 與 ISP 禁行 ---
    def process_recon_data(self, recon_data, expected_path_id="A"):
        """🧠 [分析] 接收數據並執行強化版 ISP 審計 [update: 2026-02-07]"""
        if not recon_data: return None

        try:
            current_ip = recon_data.get("ip", "?.?.?.?")
            current_org = recon_data.get("org", "Unknown")
            expected_org = PATH_CONFIG.get(expected_path_id, "Unknown")
            
            # 1. 🛡️ [核心變更：負向表列] 檢查是否為 GitHub Runner 原生環境 (絕對禁止執行的 ISP)
            # 只要偵測到 Azure 或 Microsoft， org_drift 直接設為 2.0 (致命風險)
            dangerous_isps = ["MICROSOFT", "AZURE", "AMAZON", "AWS", "GOOGLE-CLOUD"]
            is_leaking = any(danger in current_org.upper() for danger in dangerous_isps)
            
            # 2. 🛡️ [正向比對]
            is_isp_legal = (expected_org.upper() in current_org.upper())
            if expected_path_id == "B" and "CLOUDFLARE" in current_org.upper():
                is_isp_legal = True 
            # 💡 額外保險：ISP 名稱含有 "FLY" 字眼，也合法
            if "FLY" in current_org.upper():
                is_isp_legal = True

            # 2.5. ⚖️ 判定權重：0=合格, 1=Unknown/漂移, 2=致命洩漏
            if is_leaking:
                org_drift = 2.0
            elif is_isp_legal or current_org == "Unknown":
                org_drift = 0.0  # 允許 Unknown 進入主程式的再次檢查邏輯
            else:
                org_drift = 1.0         

            # --- 以下保留原有的 recon_report 建立邏輯 ---
            last_ip = self.get_last_known_ip(expected_path_id)
            unique_count = self.count_unique_ips(expected_path_id, current_ip)
            is_drifted = (last_ip is not None and last_ip != current_ip)

            # 3. 📜 [建立整合戰報]
            recon_report = {
                "ip": current_ip,
                "org": current_org,
                "is_leaking": is_leaking,        # 🚀方便除錯 
                "gateway_status": recon_data.get("gateway_status", "N/A"), # 🚀 承接 Navigator 新增的閘道數據
                "path_id": expected_path_id,
                "drift_detected": is_drifted,    # 🚀 IP 是否變動
                "org_drift": org_drift,          # 🚀 ISP 是否變動
                "unique_ip_reach": unique_count, # 🚀 該路徑目前已累積出口數
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
            
            self.data["last_recon"] = recon_report
            self.save()

            if org_drift >= 2.0:
                print(f"💀 [致命告警] 偵測到雲端原生 IP ({current_org})！身分即將曝露，強制斷電。")
            elif org_drift == 1.0:
                print(f"🚨 [嚴正告警] 路徑 ISP 異常！預期: {expected_org} | 實際: {current_org}")
            
            return recon_report
        except Exception as e:
            print(f"❌ 監視器偵察分析失敗: {e}")
            return None

    def trigger_double_check(self, nav):
        """🛰️ [備援偵察] 當第一來源為 Unknown 時，由第二 API 進行強制核查"""
        print("🔍 [備援系統] 第一來源回傳 Unknown，啟動備援 API (ip.sb) 進行二次核查...")
        try:
            # 透過導航員的 Session 發起請求，確保出口一致
            resp = nav.session.get("https://api.ip.sb/geoip", timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "ip": data.get("ip"),
                    "org": data.get("organization") or data.get("isp", "Unknown")
                }
        except:
            print("⚠️ [備援系統] 二次核查連線超時。")
        return None
    # ==========================================================================
    # --- 📊 2. 風險評估與燒毀檢查 ---
    # ==========================================================================
    def get_risk_score(self, identity_hash):
        """
        📊 計算公式：風險總分 = Σ (失敗權重 * 時間衰減)
        衰減係數：使用 24 小時半衰期策略 (lambda=0.0288)。
        """
        now = time.time()
        # 將身份 Hash 映射到 domain 結構中儲存
        i_data = self.data["domains"].get(f"id_{identity_hash}", {"failures": []})
        total_score = 0.0

        for fail in i_data["failures"]:
            t = (now - fail["timestamp"]) / 3600 # 轉換為小時
            decay = math.exp(-self.lambda_constant * t)
            total_score += fail["weight"] * decay

        return round(total_score, 2)
    
    
    def is_identity_safe(self, identity_hash):
        """
        🛡️ 解決 AttributeError：檢查身分是否安全
        """
        # 第一關：檢查 30 天硬性燒毀
        burn_time = self.data["burned_identities"].get(identity_hash)
        if burn_time:
            if (time.time() - burn_time) < 2592000: # 30天
                return False
            else:
                del self.data["burned_identities"][identity_hash] # 自動解封

        # 第二關：檢查動態衰減風險分
        score = self.get_risk_score(identity_hash)
        return score < 1.0

    
    def record_event(self, identity_hash, status_code, target_url=None, task_type="mission"):
        """🛡️ [憲兵紀錄] 分類追蹤：偵察(scout) 與 運輸(mission) [cite: 2026-02-01]"""
        host = target_url.split('/')[2] if target_url else "Unknown_Host"
        
        if "server_stats" not in self.data: self.data["server_stats"] = {}
        if host not in self.data["server_stats"]:
            # 💡 分開儲存：偵察成功/失敗 與 運輸成功/失敗
            self.data["server_stats"][host] = {
                "scout_ok": 0, "scout_fail": 0, 
                "mission_ok": 0, "mission_fail": 0
            }

        # 紀錄次數邏輯
        stats = self.data["server_stats"][host]
        is_ok = (status_code == 200)
        
        if task_type == "scout":
            if is_ok: stats["scout_ok"] += 1
            else: stats["scout_fail"] += 1
        else:
            if is_ok: stats["mission_ok"] += 1
            else: stats["mission_fail"] += 1

        # --- 3. [保留功能] 成功請求不計入身分風險分 - 
        if status_code == 200:
            self.save()
            return

        # --- 4. [保留功能] 針對伺服器拒絕進行身分權重扣分  
        weights = {403: 1.0, 429: 0.8}
        w = weights.get(status_code, 0.2)

        id_key = f"id_{identity_hash}"
        if id_key not in self.data["domains"]:
            self.data["domains"][id_key] = {"failures": []}

        self.data["domains"][id_key]["failures"].append({
            "timestamp": time.time(),
            "code": status_code,
            "weight": w
        })

        # --- 5. [保留功能] 403 身分燒毀機制  
        if status_code == 403:
            print(f"🔥 [警告] 身分曝光 ({identity_hash})！啟動 30 天燒毀。")
            self.data["burned_identities"][identity_hash] = time.time()
        
        self.save()

    
    # ==========================================================================
    # --- 📦 2.5 數據歸檔系統 (對齊週日結算) [cite: 2026-02-03] ---
    # ==========================================================================

    def finalize_weekly_archive(self, week_label):
        """📦 [戰略封存] 納入路徑歷史數據，供月報分析 IP 壽命 [cite: 2026-02-03]"""
        archive_data = {
            "week": week_label,
            "timestamp": time.time(),
            "performance_summary": self.data.get("performance_map", {}),
            "incident_logs": self.data.get("incidents", []),
            "server_stats": self.data.get("server_stats", {}),
            # 🚀  紀錄本週結束時各路徑的 IP 履歷 [02/03]
            "path_stability": self.data.get("path_history", {}) 
        }
        
        print(f"📁 [監視器] 包含路徑歷史的週快照已生成：{week_label}")
        
        # 💡 註：path_history 不歸零，因為它是跨週的身分累積指標
        self.data["incidents"] = []
        self.save()
        return archive_data 

    # ==========================================================================
    # --- 📊 3. 戰略彙整報告 (對齊 7 天周制) ---
    # ==========================================================================
    def get_weekly_summary(self):
        """📊 產生週戰略報告 (含深度取證情報) [cite: 2026-02-03]"""
        report = "📅 **Info Commander 週戰略戰報**\n"
        report += "--------------------------------\n"
        
        # A. 部隊風險評估 (Identity Risk)
        report += "🛡️ **部隊狀態 (Identity Risk):**\n"
        for id_key in self.data.get("domains", {}):
            h = id_key.replace("id_", "")
            score = self.get_risk_score(h)
            status = "🟢 安全" if score < 0.5 else ("🟡 警戒" if score < 1.0 else "🔴 暴露")
            report += f" - {id_key[:12]}.. : {status} ({score})\n"
        
        # B. 伺服器排行榜 (分開呈現偵察與運輸)
        report += "\n📡 **伺服器分項統計 (Recon vs Mission):**\n"
        server_stats = self.data.get("server_stats", {})
        if not server_stats:
            report += " (暫無紀錄)\n"
        else:
            for host, s in server_stats.items():
                report += f"📍 {host}:\n"
                report += f"  - 偵察(Scout): {s.get('scout_ok', 0)}通 / {s.get('scout_fail', 0)}拒\n"
                report += f"  - 運輸(Mission): {s.get('mission_ok', 0)}通 / {s.get('mission_fail', 0)}拒\n"

        # C. 🔥 異常事件取證報告 (Forensics)-學習伺服器防禦邏輯的核心
        report += "\n🚨 **異常事件取證 (Recent Incidents):**\n"
        incidents = self.data.get("incidents", [])
        if not incidents:
            report += " ✅ 本週無 403 攔截事件。\n"
        else:
            for i, inc in enumerate(incidents[:5], 1): # 報表僅列出最近 5 筆
                diag = inc.get("diagnostics", {})
                report += f"{i}. 🎯 目標: {inc['host']}\n"
                report += f"   🕵️ 判定: IP信譽 [{diag.get('ip_reputation', 'N/A')}] | 封锁深度 [{diag.get('ban_depth', 'N/A')}]\n"
                report += f"   🕒 時間: {inc.get('iso_time', 'N/A')[:19]}\n"
        
        # D. 🚀  路徑穩定性分析 (Path Stability)
        report += "\n🌐 **路徑穩定性分析 (Path Stability):**\n"
        path_history = self.data.get("path_history", {})
        
        if not path_history:
            report += " ✅ 所有路徑出口保持穩定。\n"
        else:
            for pid, ips in path_history.items():
                unique_count = len(set(ips))
                # 💡 判定穩定度：出口愈多愈不穩定
                stability_icon = "🟢 穩定" if unique_count < 3 else ("🟡 波動" if unique_count < 7 else "🔴 混亂")
                report += f" - 路徑 {pid} : {stability_icon} (累積出口數: {unique_count})\n"
                if ips:
                    report += f"   └─ 目前出口: {mask_ip(ips[0])}\n"
        
  
        return report
    