# To install dependencies:
#
#  $ make up
#
# To pin all installed dependencies to this file:
#
#  $ scripts/pin_pip_dependencies.sh

from setuptools import setup
import sys

needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

setup(
    name='deploy',
    include_package_data=True,
    setup_requires=pytest_runner,
    tests_require=['pytest'],
    install_requires=[
