
import bugsnag
import os
import json

from app import config
from app.logger import configure_app_logger
from app.logger import configure_db_logger
from app.logger import logging_extra
from app.logger import make_celery_logger
from app.utils.redis import StrictRedis
from app.utils.sqlalchemy_json import SQLAlchemyToJSON


from flask import copy_current_request_context
from flask import Flask
from flask import g
from flask import render_template as render_template_view
from flask import request
from flask import send_from_directory

from flask_sqlalchemy import SQLAlchemy
from flask_login import current_user
from flask_login import LoginManager


app = Flask(__name__,
            template_folder=config.TEMPLATE_FOLDER,
            static_folder=config.STATIC_FOLDER)
app.config.from_object(config)


@app.before_first_request
def configure_flask():
    """
    This is done in a method to avoid circular dependencies in the app.
    We include a lot of things in app/__init__.py but most files also
    include things from app.
    """
    from app.services.status_check import install_status_check
    install_status_check(app, "/_status")


db = SQLAlchemy(app, session_options={'expire_on_commit': False})

configure_db_logger(db.engine)
configure_app_logger(app)
celery_logger = make_celery_logger()


def log(message, level='info'):
    if message is None:
        return
    extra = logging_extra()
    extra["instance_id"] = config.INSTANCE_ID
    extra["host_ip"] = config.HOST_IP

    # PROCESS_TYPE is set in the supervisor conf file
    if os.environ.get('PROCESS_TYPE') == 'worker':
        logger = celery_logger
    else:
        logger = app.logger

    if level == 'debug':
        logger.debug(message, extra=extra)
    if level == 'info':
        logger.info(message, extra=extra)
    if level == 'error':
        logger.error(message, extra=extra)
        bugsnag.notify(Exception(message), user=extra)


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = None
login_manager.init_app(app)

# Configure Bugsnag
bugsnag.configure(
    api_key=config.BUGSNAG_API_KEY,
    notify_release_stages=["production", "test"],
    release_stage=config.ENV,
    project_root=config.ROOT_PATH
)
handle_exceptions(app)


socketio = SocketIO(app)


@socketio.on('connect', namespace='/deploys')
def connect_deploys():
    @copy_current_request_context
    def event_listener(namespace):
        r = get_redis()
        pubsub = r.pubsub()
        pubsub.subscribe(config.DEPLOYS_CHANNEL)
        for item in pubsub.listen():
            if item['type'] == 'message':
                item = json.loads(item['data'])
                key_list = item.get('key').split(':')
                if len(key_list) > 1:
                    key = key_list[1]
                    socketio.emit(key, item, namespace='/deploys')

    import gevent
    gevent.spawn(event_listener, request.namespace)


@socketio.on('disconnect', namespace='/deploys')
def disconnect_deploys():
    pass


def async_emit(redis_key, data):
    if not isinstance(data, dict):
        raise Exception("Data needs to be a dictionary.")
    data["key"] = redis_key
    data = SQLAlchemyToJSON(data).json()
    get_redis().publish(config.DEPLOYS_CHANNEL, data)


PersistentRedisConnection = StrictRedis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    decode_responses=True)


def get_redis():
    return PersistentRedisConnection


def callback(notification):

    # if you return False, the notification will not be sent to
    # Bugsnag. (see ignore_classes for simple cases)
    if isinstance(notification.exception, KeyboardInterrupt):
        return False

    notification.meta_data = {"host_ip": os.environ.get("HOST_IP")}

    if not current_user or current_user.is_anonymous:
        return
    # You can set properties of the notification and
    # add your own custom meta-data.
    notification.user = {"id": current_user.uuid,
                         "name": current_user.name,
                         "email": current_user.email_address}


bugsnag.before_notify(callback)


@login_manager.user_loader
def load_user(id):
    from app.models.user import User
    user = User.get(uuid=id)
    return user


@app.errorhandler(500)
def internal_error(exception):
    return render_template('500.html'), 500


@app.route('/static/<path:path>')
def send_js(path):
    return send_from_directory('static', path)


@app.route('/templates/<path:path>')
def send_template(path):
    return render_template(path)


@app.before_request
def before_request():
    g.requestTimeInfo = {}
    import time
    g.requestTimeInfo[request.date] = time.time()
    g.current_user = current_user


@app.after_request
def after_request(response):
    if hasattr(g, 'requestTimeInfo'):
        import time
        total = time.time() - g.requestTimeInfo[request.date]
        if total > 5:
            log("Request Complete: {} \nTotal Time: {}".format(request, total))
    return response


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


def render_template(template_name, **kwargs):
    kwargs['static_base'] = config.STATIC_BASE
    kwargs['favicon'] = "{}/opsolutely-favicon{}.png".format(config.IMAGES_BASE, config.ENVIRONMENT_SUFFIX)
    kwargs['logo'] = "{}/opsolutely-logo{}.png".format(config.IMAGES_BASE, config.ENVIRONMENT_SUFFIX)
    kwargs['env'] = config.ENV
    kwargs['images_base'] = config.IMAGES_BASE
    kwargs['app_base_link'] = config.APP_BASE_LINK
    kwargs['github_base_url'] = config.GITHUB_BASE_URL
    kwargs['kustomer_chat_api_key'] = config.KUSTOMER_CHAT_API_KEY
    kwargs['bugsnag_js_api_key'] = config.BUGSNAG_JS_API_KEY
    kwargs['current_user'] = current_user.to_dict() if current_user.is_authenticated else ''
    kwargs['user_uuid'] = current_user.get_id() if current_user.is_authenticated else ''
    kwargs['github_integration_name'] = config.GITHUB_INTEGRATION_NAME
    if request.view_args:
        kwargs['organization_uuid'] = request.view_args.get('organization_uuid', '')
        kwargs['environment_uuid'] = request.view_args.get('environment_uuid', '')
        kwargs['resource_manager_uuid'] = request.view_args.get('resource_manager_uuid', '')
        kwargs['environment_service_uuid'] = request.view_args.get('environment_service_uuid', '')
        kwargs['service_uuid'] = request.view_args.get('service_uuid', '')
        kwargs['environment_database_uuid'] = request.view_args.get('environment_database_uuid', '')
        if request.view_args.get('organization_uuid'):
            from app.utils.cache import Cache
            empty_args = Cache.get(request.view_args.get('organization_uuid'), obj_type="Organization.suspended_builds")
            if empty_args:
                for key in empty_args.keys():
                    name = empty_args[key].get('name')
                    args = empty_args[key].get('args')
                    if len(args) == 1:
                        message = "Builds have been suspended for service {} because Dockerfile arg {}" \
                                  "doesn't have a value. You can fix that " \
                                  "<a href='/organizations/{}/services/{}/'" \
                                  " target='_blank'>here</a>.".format(name,
                                                                      ', '.join(args.keys()),
                                                                      request.view_args.get('organization_uuid'),
                                                                      key)
                    else:
                        message = "Builds have been suspended for service {} because Dockerfile args {}" \
                                  "don't have values. You can fix that " \
                                  "<a href='/organizations/{}/services/{}/'" \
                                  " target='_blank'>here</a>.".format(name,
                                                                      ', '.join(args.keys()),
                                                                      request.view_args.get('organization_uuid'),
                                                                      key)
                    from flask import flash
                    flash(message, "danger")
    return render_template_view(template_name, **kwargs)


def render_json(data, response_code, **kwargs):
    return SQLAlchemyToJSON(data).json(**kwargs), response_code, {'Content-Type': 'application/json'}


def render_json_error(exception, response_code):
    message = exception.args[0] if len(exception.args) else 'error'
    return render_json({'message': message, 'success': False}, response_code)


from app import assets  # NOQA
from app.apis import *  # NOQA
from app.views import *  # NOQA