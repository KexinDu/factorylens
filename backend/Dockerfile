FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY ml ./ml
COPY data ./data
COPY backend ./backend
RUN pip install --no-cache-dir .
ENV MODEL_PATH=/app/ml/artifacts/classifier.joblib ANOMALY_MODEL_PATH=/app/ml/artifacts/anomaly_model.joblib METADATA_PATH=/app/ml/artifacts/model_metadata.json
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
