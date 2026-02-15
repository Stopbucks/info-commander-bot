# ---------------------------------------------------------
# 本程式：Podcast_outfitter，管理出勤裝備一致性(TLS, hash, header)，判斷出勤日
# ---------------------------------------------------------
import hashlib
import random
import json
import os
import time
from datetime import datetime, timezone  # 🛡️ [核心修復] 補上執行期所需的日期庫
# 🚀 修正：將 get_safe_impersonate_ver 改為 get_evolved_persona
from podcast_utils import PATH_CONFIG, mask_ip, get_evolved_persona

class TacticalOutfitter:
    """
    🎭 INFO COMMANDER - 數位人格軍需官 v4.2
    職責：管理 8 天輪迴套裝，確保 TLS 指紋、硬體參數與 User-Agent 100% 對齊。 [cite: 2026-01-16]
    """
    def __init__(self, tactics_path="config/podcast_tactics.json"):
        # 💡 指向您剛更新的戰術檔
        try:
            with open(tactics_path, "r", encoding="utf-8") as f:
                self.tactics = json.load(f)
        except Exception as e:
            print(f"❌ [軍需官] 無法讀取戰術檔: {e}")
            self.tactics = {"squad_config": {}}

        # --- 🛡️ 數位人格庫 (Persona Library) 標頭淨化，移除 ua 欄， impersonate 全權負責[2026-02-14] ---
        self.personas = {
            # 🚀 日本小隊：穩定的工作站特徵
            "FLY_JP_WORKSTATION":  {"impersonate": get_evolved_persona("JP"), "headers": {}, "jitter": (1.5, 3.5)},
            
            # 🚀 洛杉磯小隊：效能較強的桌面端
            "FLY_LA_WORKSTATION":  {"impersonate": get_evolved_persona("LA"), "headers": {}, "jitter": (1.5, 3.0)},
            
            # 🚀 GCP 擬態 (iPhone)：掌握手機設備精神，延遲拉長 (4.0 - 9.5秒)
            "GCP_IPHONE_MIMIC":    {"impersonate": "safari15_5", "headers": {}, "jitter": (4.0, 9.5)},
            
            # 🚀 GitHub 前瞻：快速反應特徵
            "GITHUB_RUNNER_EDGE":  {"impersonate": get_evolved_persona("GIT"), "headers": {}, "jitter": (1.0, 3.0)},
            
            # 🚀 救援重裝：高效率突擊
            "RESCUE_HEAVY_DESKTOP": {
                "impersonate": "chrome120", 
                "headers": {}, 
                "jitter": (1.0, 2.0)
            }
        }

    def get_squad_config(self, timestamp, force_rescue=False):
        """
        🚀 獲取裝備清單，支援 force_rescue 強制領取救援裝備。
        維護原則：區塊化邏輯、清晰辨認、支援未來進化。 [update: 2026-02-07]
        """
        
        # --- 1. [時間與索引判定] ---
        # 💡 原則：救援任務強制鎖定索引 5 (ScrapA)，其餘按 UTC 日期輪值
        if force_rescue:
            plan_index = "5"
            print(f"🛡️ [軍需官] 偵測到強制救援請求，鎖定領取 index {plan_index} (ScrapA) 裝備。")
        else:
            # 🕒 處理 UTC 時間轉日期：清晰保留轉換步驟
            dt_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            day_index = dt_utc.weekday() # 0=一, 6=日
            plan_index = str(day_index)
            print(f"📅 [軍需官] 根據 UTC 日期判定，今日出勤索引為: {plan_index}")

        # --- 2. [提取戰術計畫] ---
        # 💡 從 tactics.json 取得對應索引的內容
        plan = self.tactics['squad_config'].get(plan_index)
        
        # 🛡️ 安全檢查：若找不到計畫，給予基本的預設值，防止後續崩潰
        if not plan:
            print(f"⚠️ [警告] 找不到索引 {plan_index} 的配置，將回退至預設 Rest 模式。")
            plan = {"team": "Rest", "path_id": "R", "proxy_key": "DIRECT"}

        # --- 3. [任務態勢判定 (溫養 vs 實戰)] ---
        # 💡 邏輯：救援任務不適用溫養，必須直接領取最強武裝。
        if force_rescue:
            is_rest_day = False
            print(f"🔥 [態勢] 救援行動：直接進入實戰模式。")
        else:
            is_warmup_mode = plan.get('is_warmup', False)
            is_rest_day = (plan['team'] == "Rest" or is_warmup_mode)

        # --- 4. [數位人格著裝更新 02.12.26] ---
        # 💡 原則：救援日領取重裝；Git 小隊領取專屬 Edge 裝備；每個 Team 有自己裝備，朝向2套。
        team_name = plan.get('team', "Rest")
        
        if force_rescue:
            persona_type = "RESCUE_HEAVY_DESKTOP"
        elif "Git" in team_name:
            persona_type = "GITHUB_RUNNER_EDGE"     # 🚀 GitHub 穿 Edge
        elif "Gcp" in team_name:
            persona_type = "GCP_IPHONE_MIMIC"       # 🚀 GCP 穿 iPhone (搭配 Cloudflare)
        elif "FlyJP" in team_name:
            persona_type = "FLY_JP_WORKSTATION"     # 🚀 日本 Fly 穿日本工作站
        elif "FlyLA" in team_name:
            persona_type = "FLY_LA_WORKSTATION"     # 🚀 洛杉磯 Fly 穿美西工作站
        else:
            persona_type = "FLY_LA_WORKSTATION"     # 預設回退
            
        # ... (後續 return 邏輯維持不變) ...
       
        persona_data = self.personas.get(persona_type)
        print(f"🎭 [人格] 本次任務著裝：{persona_type}")

        # --- 5. [出口路徑對接] ---
        # 💡 邏輯：休息日使用 DIRECT；救援或實戰日領取環境變數中的 Proxy URL。
        p_key = "DIRECT" if (is_rest_day and not force_rescue) else plan['proxy_key']
        raw_val = os.environ.get(p_key, "GitHub_Runner_Direct")
        
        # 🚀 [精準對齊]：確保這裡的字串與您的 Secrets 名稱 "SCRAP_API_KEY" 完全一致
        if p_key == "SCRAP_API_KEY" and raw_val != "GitHub_Runner_Direct":
            # 💡 關鍵封裝：ScraperAPI 必須包裝成這個格式才能被 requests/curl_cffi 正確識別
            proxy_url = f"http://scraperapi:{raw_val}@proxy-server.scraperapi.com:8001"
            print(f"📡 [軍需官] ScraperAPI 代理路徑已封裝完畢。")
        else:
            proxy_url = raw_val

        # --- 6. [身分識別 Hash 生成] ---
        # 💡 原則：確保救援任務擁有獨立的身分存檔 (Cookies)，不汙染日常小隊。
        team_label = "Rescue_Ops" if force_rescue else team_name
        identity_hash = hashlib.md5(f"{team_label}_{plan.get('path_id', 'R')}".encode()).hexdigest()[:8]

        # --- 7. [最終封裝發放: 包含jitter微調] ---
        # ----徹底移除 user_agent 與冗餘 headers，根除 hardware_hints 錯誤----
        return {
            "squad_name": team_label,
            "is_warmup": is_rest_day,
            "path_id": plan.get('path_id', 'R'),
            "identity_hash": identity_hash,
            "transport_proxy": proxy_url,
            "curl_config": {
                "impersonate": persona_data["impersonate"],
                "headers": persona_data.get("headers", {}) # 💡 保持空字典，由庫生成
            },
            # 🚀 根據人格發放抖動參數，若無則回退至中立值 (1.5, 4.0)
            "micro_jitter": persona_data.get("jitter", (1.5, 4.0)),
            # 🚀 視窗精神：救援 300s, 休息 900s, 實戰 1800s
            "launch_window_max": 300 if force_rescue else (900 if is_rest_day else plan.get('launch_max', 1800))
        }
 