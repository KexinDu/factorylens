.PHONY: install data train test backend frontend docker mlflow
install:
	pip install -e ".[dev]"
	cd frontend && pnpm install
data:
	python scripts/download_data.py
train:
	python scripts/train.py
test:
	pytest
	cd frontend && pnpm test && pnpm build
backend:
	uvicorn backend.app.main:app --reload
frontend:
	cd frontend && pnpm dev
docker:
	docker compose up --build
mlflow:
	mlflow ui --backend-store-uri sqlite:///mlflow.db
