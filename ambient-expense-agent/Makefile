# Makefile for Ambient Expense Approval Agent

.PHONY: install playground test generate-traces grade

install:
	uv sync

playground:
	uv tool run google-agents-cli playground

generate-traces:
	uv run python tests/eval/generate_traces.py

grade:
	uv tool run google-agents-cli eval grade --traces artifacts/traces/generated_traces.json --config tests/eval/eval_config.yaml
