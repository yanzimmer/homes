# 多阶段构建：前端打包 + 后端运行于同一镜像

# 1) 前端构建（Vite）
FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY homes-frontend/package*.json ./
RUN npm ci
COPY homes-frontend ./
# 在构建时让前端请求相对路径 /api，便于反向代理
ENV VITE_API_BASE_URL=/api
RUN npm run build

# 2) 后端准备（复制代码即可，依赖在最终阶段安装）
FROM docker.m.daocloud.io/library/python:3.12-slim AS backend-src
WORKDIR /app
COPY Backend-System /app/Backend-System
RUN mkdir -p /app/Backend-System/sql

# 3) 运行阶段：Python + Nginx + Supervisor（单容器多进程）
FROM docker.m.daocloud.io/library/python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装运行所需软件（尽量精简）
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      nginx supervisor libgomp1 libgl1 libglib2.0-0 libsm6 libxrender1 libxext6; \
    # 移除 Debian 默认站点，避免覆盖我们自定义的 server 配置
    rm -f /etc/nginx/sites-enabled/default; \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*; \
    \
    pip install --no-cache-dir --upgrade pip; \
    pip install --no-cache-dir flask flask-cors pyjwt gunicorn; \
    # 显式安装 Paddle 运行时与 OCR 包，确保跨主机稳定
    pip install --no-cache-dir paddlepaddle==2.6.1; \
    pip install --no-cache-dir paddleocr opencv-python-headless; \
    # 预热 PaddleOCR 模型缓存（lang=ch），避免容器首启时在线下载
    python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='ch'); print('PaddleOCR prewarm OK')" || echo 'PaddleOCR prewarm skipped'; \
    rm -rf /root/.cache/pip

# 复制后端与前端构建成果
COPY --from=backend-src /app/Backend-System /app/Backend-System
COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html

# Nginx 与 Supervisor 配置
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 目录准备
RUN mkdir -p /app/Backend-System/sql /var/log/supervisor

EXPOSE 80

# 健康检查：确保 PaddleOCR 与 OpenCV 可导入
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python -c "from paddleocr import PaddleOCR; import cv2"

# 通过 Supervisor 同时运行 Nginx 与 Gunicorn
CMD ["/usr/bin/supervisord","-n","-c","/etc/supervisor/conf.d/supervisord.conf"]
