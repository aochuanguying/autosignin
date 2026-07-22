FROM python:3.11-slim

# 换清华 apt 源
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list 2>/dev/null; true

# 安装 SSH 客户端（用于 asyncssh 的 known_hosts 和密钥）和 iputils-ping
RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-client iputils-ping && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY app/ ./app/
COPY static/ ./static/

EXPOSE 3030

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3030"]
