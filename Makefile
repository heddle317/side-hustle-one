SHELL := /bin/bash

# The syntax of a Makefile is as follows:
#
# thing: otherthing
#   command
#   @silentcommand
#
# where 'thing' is a file on disk. If this file exists then `make thing` will
# say "oh, it's already there, I'll do nothing." This is because the tool is
# designed for compiling C programs into binary files.
# We (like everybody else who doesn't write C) are using it to run various
# tasks. There will never be a 'thing' file but, because it's absent, the
# `command` and `silentcommand` will always be run.
#
# 'otherthing' is another target (i.e. file on disk, but one that'll never exist) that
# we declare must be run before 'thing'. This is how you specify dependencies.
#
# `command` is any terminal command you want to run. And if you put an '@' in
# front of it then it won't be echoed to the screen.


assets:
	# If no environment has been sourced assume this is a developer running this
	# locally
	@if [ -z ${APP_BASE_LINK} ]; then \
		FLASK_APP=app ./run.sh dev flask assets build; \
	else \
		FLASK_APP=app flask assets build; \
	fi;

tags:
	ctags -R --languages=python

develop:
	@pip install -e . --process-dependency-links

up: develop

ci: flake8 test

test: setup_tests
	source local/env/test.sh && py.test -vv --durations=0 `find tests -name *test.py`

coverage: setup_tests
	rm -f .coverage
	rm -rf htmlcov
	source local/env/test.sh && py.test -vv --durations=0 --cov app `find tests -name *test.py`

html_coverage: setup_tests
	rm -f .coverage
	rm -rf htmlcov
	source local/env/test.sh && py.test --cov-report html --cov app `find tests -name *test.py`
	open htmlcov/index.html

profile_tests: setup_tests
	source local/env/test.sh && python -m cProfile -o profile `which py.test` -pep8 -v --durations=5 `find tests -name *test.py`
	# This creates a `profile` binary in the current directory that you can
	# analyze with:
	#
	#    import pstats
	#    p = pstats.Stats('profile')
	#    p.strip_dirs()
	#    p.sort_stats('tottime')
	#    p.print_stats(50)

setup_tests: 
	@# Start redis if necessary
	@&>/dev/null nc -z localhost 6379 2>/dev/null || redis-server --daemonize yes
	./run.sh test scripts/run_migrations.py

# Test any files that have changed (compared to origin/master) for pep8 violations
flake8:
	scripts/flake8.sh

# Alias for flake8
pep8: flake8

# Fix any files that have changed (compared to origin/master) for pep8 violations
autopep8:
	scripts/flake8.sh fix

# We use the same credentials in local/env/test.sh that Travis-ci.com uses by
# default.
create_test_db:
	psql postgres -c 'create database hustle_db_test;' || true


drop_test_db:
	dropdb hustle_db_test || true

reset_test_db: drop_test_db create_test_db setup_tests
