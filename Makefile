.PHONY: \
	venv install test type typecheck check \
	api ui client sdk \
	train train-save publish promote stable \
	build run product-up product-down product-logs \
	monitor-up monitor-down monitor-logs \
	compose compose-down

venv:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip

install:
	pip install -e ".[dev]"

test:
	pytest -q

type:
	mypy src

typecheck: type

check:
	pytest -q
	mypy src

api:
	SHOW_DOCS=1 INTERNAL_ONLY_ENABLED=false RATE_LIMIT_ENABLED=0 uvicorn textclf.api:app --host 127.0.0.1 --port 8000 --loop asyncio --reload

ui:
	streamlit run ui/app.py

client:
	python client_demo.py

sdk:
	openapi-python-client generate --url http://127.0.0.1:8000/openapi.json --overwrite --output-path textclf_client

train:
	python -m textclf.cli train

train-save:
	python -m textclf.cli train --save --tag local

publish:
	python -m textclf.cli publish

promote:
	python -m textclf.cli promote

stable:
	python scripts/build_stable_image.py

build:
	docker build -t textclf-api .

run:
	docker run -p 8000:8000 -v "$(PWD)/artifacts:/app/artifacts" textclf-api

product-up:
	docker compose -p textclf-product -f docker-compose.product.yml up -d

product-down:
	docker compose -p textclf-product -f docker-compose.product.yml down

product-logs:
	docker compose -p textclf-product -f docker-compose.product.yml logs -f

monitor-up:
	docker compose -p textclf-monitor -f docker-compose.monitor.yml up -d

monitor-down:
	docker compose -p textclf-monitor -f docker-compose.monitor.yml down

monitor-logs:
	docker compose -p textclf-monitor -f docker-compose.monitor.yml logs -f

compose:
	docker compose up

compose-down:
	docker compose down