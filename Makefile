.PHONY: setup run test lint clean

setup:
	python -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd backend && ../.venv/bin/python bootstrap.py

run:
	cd backend && uvicorn app.main:app --reload --port 8000

test:
	cd backend && python -m pytest tests/ -v

lint:
	ruff check backend/

clean:
	rm -f backend/data/transparency_log.jsonl backend/data/keystore.dev.json
