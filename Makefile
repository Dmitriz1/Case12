# Makefile для разработки
# =======================

PYTHON      ?= python3
PIP         ?= $(PYTHON) -m pip
BLACK       ?= $(PYTHON) -m black
ISORT       ?= $(PYTHON) -m isort
FLAKE8      ?= $(PYTHON) -m flake8
PYTEST      ?= $(PYTHON) -m pytest

SRC         = app

.PHONY: format lint test clean install hooks help

help:       ## Показать эту справку
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) \
	 | awk 'BEGIN {FS = ":.*?##"}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:    ## Установить зависимости проекта и dev-инструменты
	$(PIP) install -r requirements.txt
	$(PIP) install black isort flake8

format:     ## Запустить black + isort
	$(ISORT) $(SRC)
	$(BLACK) $(SRC)

lint:       ## flake8 + isort --check + black --check
	$(BLACK) --check $(SRC)
	$(ISORT)  --check-only $(SRC)
	$(FLAKE8) $(SRC)

test:       ## Запустить все тесты
	$(PYTEST) -q

clean:      ## Удалить *.pyc и кеши
	find . -name '__pycache__' -prune -exec rm -r {} +
	find . -name '*.py[co]' -delete
