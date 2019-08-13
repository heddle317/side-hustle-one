from datetime import timedelta
import inspect
import os
import sys

'''
Check if our environment keys haven't been sourced yet and give guidance on fixing that
'''
if os.environ.get('APP_BASE_LINK') is None:
    print("""
    Environment variables not found!
    You must run the app and any scripts either in AWS (where the environment
    variables are already loaded into `env`) or as an argument to ./run.sh:
    ./run.sh dev                   # starts the app on your machine in local mode
    ./run.sh dev python script.py  # sources env/local.sh and then runs `python script.py`
    ./run.sh dev gunicorn          # sources env/local.sh and then runs `gunicorn`
    """)
    sys.exit(1)


# /where/you/put/side-husle-one
RootPath = os.path.dirname(
    os.path.dirname(
        os.path.abspath(
            inspect.getfile(
                inspect.currentframe()
            )
        )
    )
)


'''
FOLDER SETTINGS  (This must be first)
'''
PROJECT_PATH = os.path.realpath(os.path.dirname(__file__))
ROOT_PATH = BASE_DIR = os.path.join(os.path.dirname(__file__), '..')

'''
FLASK APP  (This must be second)
'''
APP_BASE_LINK = os.environ['APP_BASE_LINK']
PUBLIC_API_BASE_LINK = os.environ.get('PUBLIC_API_BASE_LINK') or APP_BASE_LINK
BLOG_BASE_LINK = os.environ.get('BLOG_BASE_LINK')
CACHE_DISABLED = os.environ.get('CACHE_DISABLED', False)
COMMIT_HASH = os.environ.get('COMMIT_HASH')
CSRF_ENABLED = True
DEPLOYS_CHANNEL = 'socketIO-deploys'
HOST_IP = os.environ.get('HOST_IP')
INSTANCE_ID = os.environ.get('INSTANCE_ID')
MODEL_HASH = os.environ['MODEL_HASH']
# Port is 7051 in local,
#         7052 in test
PORT = int(os.environ.get('PORT', '7051'))
SECRET_KEY = os.environ['SECRET_KEY']
STATIC_FOLDER = os.path.join(ROOT_PATH, 'static')
TEMPLATE_FOLDER = os.path.join(ROOT_PATH, 'templates')

'''
ENVIRONMENT  (This must be third)
'''
ENV = os.environ['ENVIRONMENT']
UNIT_TESTING = os.environ.get('UNIT_TESTING', False)

SESSION_COOKIE_NAME = "session_cookie_name" + ENV
ENVIRONMENT_SUFFIX = ''

# Cast this value to a boolean because SQLAlchemy picks it up
DEBUG = not not os.environ.get('DEBUG', False)
LOG_PATH = os.path.join(ROOT_PATH, 'logs')

if ENV == 'local':
    DEBUG = True
    LOG_PATH = os.path.join(ROOT_PATH, 'logs')
    STATIC_BASE = '{}/static'.format(APP_BASE_LINK)
    REDIS_PORT = PORT - 6000  # port 1051 is defined in local/supervisor_local.conf
    GITHUB_INTEGRATION_NAME = os.environ.get(
        'GITHUB_INTEGRATION_NAME', 'opsolutely-dev')
    GITHUB_INTEGRATION_ID = int(os.environ.get('GITHUB_INTEGRATION_ID', 670))
    ENVIRONMENT_SUFFIX = '-dev'
elif ENV in ['test', 'staging']:
    # TODO: break apart staging and test to use different ENV values
    if UNIT_TESTING:
        LOG_PATH = os.path.join(ROOT_PATH, 'logs')
    else:
        LOG_PATH = '/var/log'
    REDIS_PORT = 6379
    GITHUB_INTEGRATION_NAME = 'opsolutely-test'
    GITHUB_INTEGRATION_ID = 669
    ENVIRONMENT_SUFFIX = '-staging'
else:
    LOG_PATH = '/var/log'
    REDIS_PORT = 6379
    GITHUB_INTEGRATION_NAME = 'opsolutely'
    GITHUB_INTEGRATION_ID = 668

'''
AWS
'''
AWS_ACCOUNT_ID = os.environ['AWS_ACCOUNT_ID']
AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
IMAGE_BUCKET = os.environ['IMAGE_BUCKET']
S3_BUCKET = os.environ['S3_BUCKET']
S3_BASE = 'https://s3.amazonaws.com'
SERVICE_ROLE_ARN = os.environ['SERVICE_ROLE_ARN']
STATIC_BUCKET = os.environ['STATIC_BUCKET']

IMAGES_BASE = '{}/{}'.format(S3_BASE, IMAGE_BUCKET)
STATIC_BASE = '{}/{}'.format(S3_BASE, STATIC_BUCKET)

'''
BUGSNAG
'''
BUGSNAG_API_KEY = os.environ.get('BUGSNAG_API_KEY')
BUGSNAG_JS_API_KEY = os.environ.get('BUGSNAG_JS_API_KEY')

'''
SQLALCHEMY
'''
SQLALCHEMY_MIGRATE_REPO = os.path.join(ROOT_PATH, 'db_repository')
SQLALCHEMY_POOL_RECYCLE = 3600
SQLALCHEMY_ECHO = DEBUG
SQLALCHEMY_TRACK_MODIFICATIONS = False
POSTGRES_ENV_POSTGRESQL_DB = os.environ['POSTGRES_ENV_POSTGRESQL_DB']
SQLALCHEMY_DATABASE_URI = 'postgresql://{}:{}@{}:{}/{}'.format(os.environ['POSTGRES_ENV_POSTGRES_USER'],
                                                               os.environ['POSTGRES_ENV_POSTGRES_PASSWORD'],
                                                               os.environ['POSTGRES_PORT_5432_TCP_ADDR'],
                                                               os.environ['POSTGRES_PORT_5432_TCP_PORT'],
                                                               POSTGRES_ENV_POSTGRESQL_DB)
