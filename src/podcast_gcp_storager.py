# ---------------------------------------------------------
# 本程式碼為：Podcast_gcp_storager，負責GCP 相關邏輯判定
# ---------------------------------------------------------
import os
import json
from google.cloud import storage
from google.oauth2 import service_account

class GCPStorageManager:
    """
    🏗️ [大腦連結] GCP 儲存管理員 v1.1
    職責：管理雲端記憶同步，確保 podcast_monitor.json 在不同環境具備持久性。
    """
    def __init__(self, bucket_name="info-commander-vault"):
        self.bucket_name = bucket_name
        # 取得 GitHub Secrets 中的 JSON 憑證字串 [cite: 2026-01-31]
        self.json_key = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        self.client = self._init_client()

    def _init_client(self):
        """利用 JSON 金鑰初始化 GCP 連線"""
        if not self.json_key:
            print("⚠️ [GCP] 環境變數缺失，系統將運行於本地模式。")
            return None
        try:
            credentials_info = json.loads(self.json_key)
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            return storage.Client(credentials=credentials)
        except Exception as e:
            print(f"❌ [GCP] 金鑰憑證解析失敗: {e}")
            return None

    def download_memory(self, local_path, cloud_filename="podcast_monitor.json"):
        """任務啟動前：從愛荷華基地拉取最新的指紋紀錄 [cite: 2026-01-31]"""
        if not self.client: return False
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(cloud_filename)
            if blob.exists():
                blob.download_to_filename(local_path)
                print(f"📥 [GCP] 成功取回雲端記憶：{cloud_filename}")
                return True
            print("ℹ️ [GCP] 雲端尚無存檔，將由本地建立初始紀錄。")
        except Exception as e:
            print(f"⚠️ [GCP] 下載過程異常: {e}")
        return False

    def upload_memory(self, local_path, cloud_filename="podcast_monitor.json"):
        """
        ☁️ [運輸兵] 將本地記憶檔案同步回 GCP Bucket [cite: 2026-01-31]
        """
        if not self.client: return False
        
        # 🛡️ 檔案存在性預檢
        if not os.path.exists(local_path):
            print(f"⚠️ [GCP] 找不到本地記憶檔案，放棄回填: {local_path}")
            return False
            
        try:
            # 💡 修正點：必須從 client 中取得 bucket 物件
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(cloud_filename)
            
            # 💡 [除錯監控點] 輸出詳細上傳目標
            print(f"📤 [GCP Debug] 啟動記憶回填機制...")
            print(f"   └─ 本地路徑: {local_path}")
            print(f"   └─ 目標 Bucket: {self.bucket_name}")
            print(f"   └─ 雲端檔名: {cloud_filename}")
            
            # 執行上傳
            blob.upload_from_filename(local_path)
            return True
            
        except Exception as e:
            # 🛡️ 捕捉精確報錯：如 403 Forbidden (權限錯誤)
            print(f"🛑 [GCP Error] 回填中斷！詳細資訊: {str(e)}")
            return False