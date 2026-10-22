.PHONY: install run test lint format demo docker

install:
	pip install -e ".[dev]"

run:
	uvicorn ro_aging.api:app --reload

test:
	pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

demo:
	python scripts/build_static_demo.py

docker:
	docker compose up --build
