FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /workspace/backend
COPY pyproject.toml requirements.lock ./
COPY app ./app
RUN pip install -c requirements.lock . && useradd --create-home --uid 10001 autojob
COPY alembic.ini ./
COPY alembic ./alembic
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh && mkdir -p /workspace/storage/cv /workspace/context && chown -R autojob:autojob /workspace
USER autojob
EXPOSE 8000
CMD ["./entrypoint.sh"]
