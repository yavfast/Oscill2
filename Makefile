SHELL := /bin/bash
PY ?= python3
VENV := .venv
PIP := $(VENV)/bin/pip
PYTHON := $(VENV)/bin/python

.PHONY: venv install upgrade freeze clean-venv

venv:
	@echo "Creating virtual environment in $(VENV)"
	@$(PY) -m venv $(VENV)
	@echo "Activate with: source $(VENV)/bin/activate"

install: venv
	@echo "Upgrading pip and installing requirements"
	@$(PIP) install -U pip wheel
	@$(PIP) install -r requirements.txt

upgrade:
	@echo "Upgrading all dependencies to latest compatible versions"
	@$(PIP) install -U -r requirements.txt

freeze:
	@$(PIP) freeze > requirements.lock.txt
	@echo "Locked dependencies written to requirements.lock.txt"

clean-venv:
	@echo "Removing $(VENV)"
	@rm -rf $(VENV)
