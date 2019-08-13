#!/usr/bin/env python
import sys
import os
# from pgcli.main import cli

"""
Provides direct access to the current environment's postgres database.
Safe for use in local and unit test environments.
Be careful in dev environment (it's shared between developers)
Avoid using this on test.opsolutely.com or opsolutely.com except in an
emergency. Do use this in AWS you'll first need to ssh to the
environment in which this file is deployed and then run this:
    mac> $./run.sh dev scripts/ssh_to_env.py 16971ff3-1687-451e-8633-2e69ef1fa1f7
    # SSH to any host running a Deploy instance
    aws> $ ssh 10.1.1.113
    # execute this file on any docker instance (assuming we're only
    # running this app on that box)
    aws> $ docker exec $(docker ps | tail -n 1 | awk '{print($1}') ./run.sh test scripts.psql.py)
"""
if __name__ == '__main__':
    user = os.environ.get('POSTGRES_ENV_POSTGRES_USER', False)
    db = os.environ.get('POSTGRES_ENV_POSTGRESQL_DB', False)
    pw = os.environ.get('POSTGRES_ENV_POSTGRES_PASSWORD', False)
    host = os.environ.get('POSTGRES_PORT_5432_TCP_ADDR', False)
    port = os.environ.get('POSTGRES_PORT_5432_TCP_PORT', False)

    if user is not False and db is not False and pw is not False and host is not False and port is not False:
        cmd = 'PGPASSWORD={} psql -h {} -p {} -U {} {}'.format(pw, host, port, user, db)
        for arg in sys.argv[1:]:
            print(arg)
            cmd += ' "{}"'.format(arg)
        os.system(cmd)
    else:
        scriptName = os.path.basename(__file__)
        print("Usage: ./run.sh ENV {}".format(scriptName))
        sys.exit(1)
