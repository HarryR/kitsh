PYTHON ?= python
NAME ?= kitsh

all: coverage

lint:
	$(PYTHON) -mpyflakes $(NAME)

analint: lint
	$(PYTHON) -mpylint --reports=n -d broad-except,bad-continuation,trailing-whitespace,missing-docstring $(NAME) || true

client:
	$(PYTHON) -m$(NAME).client

clean:
	rm -rf coverage
	find . -name '*.pyc' -exec rm -f '{}' ';'
	find . -name '__pycache__' -type d -exec rm -rf '{}' ';' || true

test: lint
	$(PYTHON) -mpytest tests/

coverage: lint
	$(PYTHON) -mpytest --cov-report html:coverage --cov=$(NAME) tests/

view-coverage: coverage
	x-www-browser coverage/index.html

webui:
	$(PYTHON) -m$(NAME).webui -v

docker-build:
	docker build -t $(NAME)/$(NAME) .
