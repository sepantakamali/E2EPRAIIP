.PHONY: venv install test type api train save build run compose

venv:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip

install:
	pip install -e ".[dev]"

test:
	pytest -q

type:
	mypy src

api:
	uvicorn textclf.api:app --reload --port 8000

train:
	python -m textclf.cli

save:
	python -m textclf.cli --save --tag local

build:
	docker build -t textclf-api .

run:
	docker run -p 8000:8000 -v "$(PWD)/artifacts:/app/artifacts" textclf-api

compose:
	docker compose up

stable:
	python scripts/build_stable_image.py

monitor-up:
\tdocker compose -f docker-compose.monitor.yml up -d

monitor-down:
\tdocker compose -f docker-compose.monitor.yml down

monitor-logs:
\tdocker compose -f docker-compose.monitor.yml logs -f api prometheus grafana