FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

COPY app /app/app
COPY scripts /app/scripts
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8010

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
