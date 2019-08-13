#!/bin/bash
#
# This script sources the appropriate environment variables and then executes
# whatever comes after like a normal command.
# Examples:
#
#   python some/script.py # blows up! No AWS_ACCESS_KEY set!
#   ./run.sh dev python some/script/py # works!
#   source local/env/local.sh
#   ./run.sh python some/script/py # Also works! You can leave off the environment if
#
#   gunicorn  # blows up! the app can't boot!
#   ./run.sh gunicorn # works!


# Exit script if any line exists with non-zero status
set -e

export PYTHONPATH=.:$PYTHONPATH

if [[ 'Darwin' == $(uname) ]] && [[ -z $VIRTUAL_ENV ]]; then
  1>&2 echo "No virtualenv is set. Maybe you want to try \`workon deploy\` first?"
  exit 1
fi

current_directory=$(cd $(dirname $0) && pwd)
command=$1

ensure_packages_are_updated() {
    # The point of this function is to run `python setup.py --process-dependency-links`
    # Since that's a slow operation we update the timestamp on an empty cache
    # file every time we do it and then we check if setup.py has been changed
    # since we last updated things
    local timestamp_cache=./.cache/setup.py-timestamp

    mkdir -p .cache
    [[ -f $timestamp_cache ]] || touch -f $timestamp_cache

    if [[ 'setup.py' == $(ls -1t ${timestamp_cache} setup.py | head -n 1) ]]; then
      # Setup.py has been updated more recently than this function has been called
      echo "Ensuring your dependencies match setup.py:"
      echo "> pip install -e . --process-dependency-links"
      pip install -e . --process-dependency-links &>/dev/null
      touch -m $timestamp_cache
    fi

    # and make sure the redis backup is clear
    rm -f dump.rdb
}


case $command in
  local)
    source ./local/env/local.sh
    # If no other arguments are passed then start the app
    if [[ 1 == "$#" ]]; then
      ensure_packages_are_updated
      ./local/web.py
      # exec supervisord -c ./local/supervisor_local.conf
    fi
    ;;

  test)
    source ./local/env/test.sh
    # If no other arguments are passed then explain how this
    if [[ 1 == "$#" ]]; then
      echo "Usage: ${0} test some_command"
      echo "This is for unit tests"
      exit 1
    fi
    ;;

  # Show usage if no arguments were passed, the first argument wasn't an
  # environment; and no environment has already been sourced.
  *)
    if [[ -z $AWS_SECRET_ACCESS_KEY ]]; then
      1>&2 echo "Usage: ${0} ENV CMD"
      1>&2 echo ""
      1>&2 echo "  Environments:"
      1>&2 echo "    local: start a server using postgres on your machine"
      1>&2 echo "  CMD = anything you'd normally run as a command"
      1>&2 echo ""
      1>&2 echo "  Example:"
#       1>&2 echo "    ${0} dev scripts/add_user.py kate@opsolutely.com 'Kate Heddleston'"
      1>&2 echo ""
      exit 1
    fi
    ;;

esac


# If we got to here then there was more than one argument and it is a
# command that needs to be executed. An local/env/*.sh file has been sourced
# and now we just execute the rest of the arguments as a command.
set -x
exec "${@:2}"