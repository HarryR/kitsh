PYTHON ?= python
NAME ?= kitsh
WWW_BROWSER = x-www-browser
COVERAGE ?= $(PYTHON) -mcoverage
COVERAGE_RUN ?= PYTHONPATH=. $(COVERAGE) run -a

all: coverage

lint:
	$(PYTHON) -mpyflakes $(NAME)

analint: lint
	$(PYTHON) -mpylint --reports=n -d broad-except,bad-continuation,trailing-whitespace,missing-docstring $(NAME) || true

client:
	$(PYTHON) -m$(NAME).client

clean:
	rm -rf coverage build dist $(NAME).egg-info
	find . -name '*.pyc' -exec rm -f '{}' ';'
	find . -name '__pycache__' -type d -exec rm -rf '{}' ';' || true

test: lint
	$(PYTHON) -mpytest tests/

coverage: lint
	$(PYTHON) -mpytest --cov-report html:coverage --cov=$(NAME) tests/

coverage-html:
	$(COVERAGE) html

coverage-view:
	$(WWW_BROWSER) coverage/index.html

webui:
	$(PYTHON) -m$(NAME).webui -v

webui-coverage:
	PYTHONPATH=. $(COVERAGE_RUN) -m kitsh.webui

docker-build:
	docker build -t $(NAME)/$(NAME) .
