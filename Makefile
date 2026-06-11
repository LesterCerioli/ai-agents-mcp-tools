PYTHON  := venv/bin/python
PIP     := venv/bin/pip
UVICORN := venv/bin/uvicorn
PYTEST  := venv/bin/pytest
RUFF    := venv/bin/ruff

HOST    ?= 0.0.0.0
PORT    ?= 3443

.PHONY: install dev run stop test lint format help

install:
	$(PIP) install -e ".[dev]"

dev:
	$(UVICORN) app.api.main:app --host $(HOST) --port $(PORT) --reload

run:
	$(UVICORN) app.api.main:app --host $(HOST) --port $(PORT)

stop:
	-kill $$(lsof -ti:$(PORT)) 2>/dev/null && echo "Stopped" || echo "Nothing running on port $(PORT)"

test:
	$(PYTEST) tests/ -v

test-fast:
	$(PYTEST) tests/ -q

lint:
	$(RUFF) check src/ tests/

format:
	$(RUFF) format src/ tests/

help:
	@echo "make install   — install package and dev dependencies"
	@echo "make dev       — start API with hot-reload  (HOST=$(HOST) PORT=$(PORT))"
	@echo "make run       — start API without reload"
	@echo "make test      — run full test suite"
	@echo "make test-fast — run tests (quiet output)"
	@echo "make stop      — kill process on port $(PORT)"
	@echo "make lint      — run ruff linter"
	@echo "make format    — run ruff formatter"
