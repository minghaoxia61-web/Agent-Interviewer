# 多阶段构建：前端打包后由 FastAPI 静态托管，单容器部署
FROM node:20-alpine AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
# ensurepip 离线升级：slim 自带的 pip 24.0 不支持 Metadata-Version 2.4
# （langgraph>=0.6 等包会报 "is not a supported wheel ... can't be sorted"）
RUN python -m ensurepip --upgrade && \
    pip install --no-cache-dir -r requirements.txt
COPY app/ ./app
COPY data/ ./data
COPY --from=ui /ui/dist ./static

# 7860 = Hugging Face / 魔搭创空间的约定端口；Render 等平台会注入 PORT 环境变量覆盖此默认值
ENV PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
