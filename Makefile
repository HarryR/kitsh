PYTHON ?= python
NAME ?= metsh

all: coverage

lint:
	$(PYTHON) -mpyflakes $(NAME)

analint: lint
	$(PYTHON) -mpylint --reports=n -d broad-except,bad-continuation,trailing-whitespace,missing-docstring $(NAME) || true

client:
	$(PYTHON) -m$(NAME).client

clean:
	find . -name '*.pyc' -exec rm -f '{}' ';'
	find . -name '__pycache__' -type d -exec rm -rf '{}' ';'

test: lint
	$(PYTHON) -mpytest tests/

coverage: lint
	$(PYTHON) -mpytest --cov-report html:coverage --cov=metsh tests/

webui:
	$(PYTHON) -m$(NAME).webui -v

docker-build:
	docker build -t $(NAME)/$(NAME) .