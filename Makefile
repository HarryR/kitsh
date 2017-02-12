PYTHON ?= python3

all:
	@echo "doop"

lint:
	$(PYTHON) -mpyflakes metadock

compile:
	$(PYTHON) -mpylint metadock

clean:
	find . -name '*.pyc' -exec rm -f '{}' ';'
