# ragent-py 智能客服后端镜像
# 构建：docker build -t ragent-py .
# 运行：docker run --rm -p 8000:8000 --env-file .env ragent-py
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# onnxruntime 依赖
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "bootstrap.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
