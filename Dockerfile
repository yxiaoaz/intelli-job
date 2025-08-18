# https://hub.docker.com/_/python
FROM python:3.13


ENV APP_HOME /app
WORKDIR $APP_HOME

# 将本地代码拷贝到容器内
COPY . .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV GUNICORN_WORKERS=1
ENV GUNICORN_THREADS=4
ENV GUNICORN_TIMEOUT=60

# 安装依赖到指定的/install文件夹
RUN python -m pip install --upgrade pip
RUN pip cache purge
RUN pip install --no-cache-dir -r requirements.txt --retries 10

EXPOSE 5002
# 启动 Web 服务
# 如果您的容器实例拥有多个 CPU 核心，我们推荐您把线程数设置为与 CPU 核心数一致
CMD exec gunicorn --bind :5002 --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --timeout ${GUNICORN_TIMEOUT} main:server