.PHONY: install hooks fmt lint typecheck test check inspect

install:
	uv sync

hooks:
	uvx pre-commit install --hook-type pre-commit --hook-type commit-msg

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run pyright

test:
	uv run pytest

check: lint typecheck test

inspect:
	npx @modelcontextprotocol/inspector uv run notability-mcp serve
