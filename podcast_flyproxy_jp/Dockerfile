# 使用輕量級 Python 3.9
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 複製當前目錄檔案進去
COPY . .

# 安裝代理軟體
RUN pip install --no-cache-dir -r requirements.txt

# 啟動指令：
# --hostname 0.0.0.0 : 允許外部連線 (必須)
# --port 8080 : 監聽 8080 端口
# --basic-auth : 設定帳號密碼 (會從 Fly 的環境變數讀取)
CMD proxy --hostname 0.0.0.0 --port 8080 --basic-auth $PROXY_USER:$PROXY_PASS