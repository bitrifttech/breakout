#!/usr/bin/make -f
# Simple Makefile for Orchestrator project

PYTHON ?= python3
ORCH := orchestrator/main.py
SCORER := scoring/scorer.py
RUNS_DIR := runs
DELIM ?= ---
CONTAINER ?= breakout_agent

.PHONY: help tests test up down smoke score latest-run show-latest-events show-latest-meta ls-container

help:
	@echo "Targets:"
	@echo "  tests                 Alias for 'test'"
	@echo "  test                  Run unit tests"
	@echo "  up                    Start docker compose"
	@echo "  down                  Stop docker compose"
	@echo "  smoke                 Run non-interactive 3-step smoke test (delimited mode)"
	@echo "  score                 Score the latest run in $(RUNS_DIR)/"
	@echo "  latest-run            Print latest run directory path"
	@echo "  show-latest-events    Print latest run events.jsonl"
	@echo "  show-latest-meta      Print latest run meta.json"
	@echo "  ls-container          List /, /world, /home/agent inside container"

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

tests: test

up:
	docker compose up -d

down:
	docker compose down

# Non-interactive smoke test using delimited mode
# Requires container to be running. Uses BLOCK_DELIM=$(DELIM)
smoke: up
	LLM_MODE=delimited BLOCK_DELIM=$(DELIM) $(PYTHON) $(ORCH) < smoke/protocol.txt

# Score the latest run directory
score:
	@events_dir=$$(ls -1dt $(RUNS_DIR)/* 2>/dev/null | head -n1); \
	[ -n "$$events_dir" ] && $(PYTHON) $(SCORER) "$$events_dir" || echo "No runs found"

latest-run:
	@ls -1dt $(RUNS_DIR)/* | head -n1

show-latest-events:
	@events_dir=$$(ls -1dt $(RUNS_DIR)/* | head -n1); \
	[ -n "$$events_dir" ] && cat "$$events_dir/events.jsonl" || echo "No runs found"

show-latest-meta:
	@events_dir=$$(ls -1dt $(RUNS_DIR)/* | head -n1); \
	[ -n "$$events_dir" ] && cat "$$events_dir/meta.json" || echo "No runs found"

ls-container:
	docker exec $(CONTAINER) /bin/bash -lc 'ls -la / /world /home/agent'
