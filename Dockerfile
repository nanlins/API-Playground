FROM python:3.13-slim

WORKDIR /app

# 构建期 pip 源可覆盖（国内加速：--build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple）；默认官方源保证 CI 一致性
ARG PIP_INDEX_URL=https://pypi.org/simple

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} --retries 8 --timeout 60 -r requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

# 修改记录：
#   2026-10-01 新增 PIP_INDEX_URL 构建参数（默认官方源，国内可用镜像源加速）；pip 增加 --retries/--timeout 抗镜像限流
