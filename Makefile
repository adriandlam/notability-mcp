.PHONY: install hooks fmt lint typecheck test check codegen inspect

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

# Regenerate FlatBuffers accessors after editing schema/notability-ops.fbs.
codegen:
	rm -rf src/notability_mcp/_generated
	flatc --python --gen-onefile -o src/notability_mcp/_generated schema/notability-ops.fbs
	touch src/notability_mcp/_generated/__init__.py

inspect:
	npx @modelcontextprotocol/inspector uv run notability-mcp serve
