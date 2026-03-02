# 使用 Python 3.9 輕量版
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 複製依賴清單
COPY requirements.txt .

# 安裝套件
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼 (配合 .dockerignore 排除不必要檔案)
COPY . .

# 暴露您的程式碼指定的 10000 Port
EXPOSE 10000

# 啟動命令
CMD ["python", "app.py"]