.DEFAULT_GOAL := check

VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip
PYTEST ?= $(VENV)/bin/pytest
MYPY ?= $(VENV)/bin/mypy
UVICORN ?= $(VENV)/bin/uvicorn
STREAMLIT ?= $(VENV)/bin/streamlit
OPENAPI_GENERATOR ?= $(VENV)/bin/openapi-python-client

.PHONY: \
	venv install test type typecheck check \
	api ui client sdk audit-models reconcile-models \
	train train-save publish promote \
	build run product-up product-down product-logs \
	monitor-up monitor-down monitor-logs \
	compose compose-down

venv:
	python3 -m venv "$(VENV)"
	$(PYTHON) -m pip install -U pip

install:
	$(PIP) install -e ".[dev]"

test:
	$(PYTEST) -q

type:
	$(MYPY) src admin

typecheck: type

check:
	$(PYTEST) -q
	$(MYPY) src admin

api:
	SHOW_DOCS=1 INTERNAL_ONLY_ENABLED=false RATE_LIMIT_ENABLED=0 $(UVICORN) textclf.api:app --host 127.0.0.1 --port 8000 --loop asyncio --reload

ui:
	$(STREAMLIT) run ui/app.py

client:
	$(PYTHON) client_demo.py

sdk:
	$(OPENAPI_GENERATOR) generate --url http://127.0.0.1:8000/openapi.json --overwrite --output-path textclf_client

audit-models:
	$(PYTHON) -m scripts.audit_model_registry

reconcile-models:
	$(PYTHON) -m scripts.audit_model_registry --reconcile

train:
	$(PYTHON) -m textclf.cli train

train-save:
	$(PYTHON) -m textclf.cli train --save --tag local

publish:
	@test -n "$(ARTIFACT)" || (echo "Usage: make publish ARTIFACT=artifacts/model.joblib PUBLISH_ARGS='--release-tag v1.0'" && exit 2)
	$(PYTHON) -m textclf.cli publish "$(ARTIFACT)" $(PUBLISH_ARGS)

promote:
	@test -n "$(ARTIFACT)" || (echo "Usage: make promote ARTIFACT=artifacts/model.joblib" && exit 2)
	$(PYTHON) -m textclf.cli promote "$(ARTIFACT)"

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
