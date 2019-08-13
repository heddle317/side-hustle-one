#!/bin/bash

set -o pipefail

operation=$1
compare_to=$2

if [[ -n $compare_to ]]; then
  merge_base=$compare_to
else
  merge_base=$(git merge-base origin/master HEAD)
fi

modified_files=$(git diff --name-only ${merge_base} | egrep \.py\\\b)
if [[ -z ${modified_files} ]]; then
    exit 0
fi

real_files=$(find ${modified_files} 2>/dev/null)

set -u

case $operation in
  fix)
    exec autopep8 -a -i ${real_files:-app/__init__.py}
    ;;
  check)
    exec flake8 ${real_files:-app/__init__.py}
    ;;
  *)
    exec flake8 ${real_files:-app/__init__.py}
    ;;
esac