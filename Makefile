#!make

test:
	@echo "--> Running Python Tests with Coverage"
	coverage run --branch -m pytest -vv || exit 1
	coverage report -m
	@echo ""
