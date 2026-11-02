FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-hashes -o requirements.txt && uv pip install --system -r requirements.txt
COPY . .
RUN chmod +x start.sh && useradd --create-home spendzer && chown -R spendzer /app
USER spendzer
EXPOSE 8000
CMD ["./start.sh"]
