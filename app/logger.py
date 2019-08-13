import bugsnag
import inspect
import logging
import re
import traceback

from app import config
from app.utils.ansi_color_formatter import AnsiColorFormatter

from flask import session
from flask_login import current_user

from logging.handlers import RotatingFileHandler

from sqlalchemy import event

application_log_filename = '{}/application-{}.log'.format(
    config.LOG_PATH, config.ENV)
application_debug_log_filename = '{}/application-debug-{}.log'.format(
    config.LOG_PATH, config.ENV)
celery_log_filename = '{}/celery-{}.log'.format(config.LOG_PATH, config.ENV)


def configure_app_logger(app):
    app.logger.addHandler(colored_log_handler(application_log_filename))
    app.logger.findCaller = app_caller
    if config.DEBUG:
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.setLevel(logging.INFO)


def make_celery_logger():
    celery_logger = logging.getLogger('celery_logger')
    celery_logger.addHandler(colored_log_handler(celery_log_filename))
    if config.DEBUG:
        celery_logger.setLevel(logging.DEBUG)
    else:
        celery_logger.setLevel(logging.INFO)
    celery_logger.findCaller = app_caller
    return celery_logger


def configure_db_logger(engine):
    # Connect the Flask app's logging to SQLAlchemy's only in local 
    if not config.DEBUG:
        return

    # if config.SQLALCHEMY_ECHO is set then db.engine.logger is actually
    # a wrapper. Let's unwrap it.
    logger = engine.logger
    if hasattr(logger, 'logger'):
        logger = logger.logger

    # We remove the existing STDOUT handler
    del logger.handlers[:]

    logger.addHandler(colored_log_handler(application_debug_log_filename))
    # Uncomment the following to get colored SQL logging in your IPython session
    # logger.addHandler(colored_stdout_handler())
    # Print logs to stdout
    logger.setLevel(logging.DEBUG)

    # And then we walk up the hierarchy of loggers and remove
    # `logging.RootLogger` (the default return value of
    # `logging.getLogger()`) from the hierarchy because it'll print
    # everything to STDOUT
    root_logger = logging.getLogger()
    parent = logger.parent
    while parent.parent != root_logger:
        parent = parent.parent
    # snip, now there's only SQLAlchemy loggers in a parent hierarchy
    parent.parent = None

    @event.listens_for(engine, 'before_cursor_execute', retval=True)
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """
        Appends the line that triggered this SQL as a comment on the
        statement itself
        """
        filename, line, source = app_caller(None)
        if line and line > 0:
            comment = "{}:{} {}".format(filename, line, source)
            statement = statement + ' -- ' + comment
        return statement, parameters


class SparseRotatingFileHandler(RotatingFileHandler):
    """
    Rotates files when they get too big and doesn't print blank lines to
    the log. So the following does nothing:
        log('', level='info')
    """

    # Increase this to see the actual values we use when querying the
    # db. Note that verbosity of 1 is fine even in production but any
    # higher than that and we'll leak user data so keep it to
    # environments without any sensitive content.
    verbose = False

    def emit(self, record):
        message = record.getMessage()
        if message == '{}':
            # This is an empty line
            return
        elif len(record.args) and len(record.args[0].params) and not self.verbose:
            # This is a line containing parameters to interpolate into
            # the previous SQLAlchemy query printed on the screen. Let's
            # skip this.
            return
        try:
            return super(SparseRotatingFileHandler, self).emit(record)
        except FileNotFoundError:
            # log rotation happened *just* this moment
            pass


def logging_extra():
    try:
        extra = {'session_id': '[NO SESSION ID]',
                 'user_email': '[NO USER EMAIL]'}
        if session:
            extra['session_id'] = session.get('_id', '')[:24]
        if current_user and current_user.is_authenticated:
            extra['user_email'] = current_user.email_address
        return extra
    except BaseException as e:
        bugsnag.notify(e)
        return {}


def app_caller(stackInfo):
    """
    Given a stack trace return the first line that is likely to be
    actual app code. The return value matches the form expected by
    Python's built-in logging module's 'findCaller' method:
        fn, lno, func = self.findCaller()
    Please edit freely.
    """
    if stackInfo:
        print(stackInfo)

    frame = inspect.currentframe()
    for filename, line, func, source in traceback.extract_stack(frame):
        # Find the first line that's actually our code but is not in a
        # generic helper method.
        if re.search('(app|tests)/.*.py', filename) \
                and not re.search('app/logger.py', filename) \
                and not re.search('models/__init__.py', filename) \
                and not (re.search('app/__init__.py', filename) and (line > 50 and line < 100))\
            return (filename.replace(config.RootPath + '/', ''), line, source, )
    return ('(no source file)', -1, '', )


colored_log_formatter = AnsiColorFormatter("%(levelname)s %(asctime)s: %(instance_id)s-%(host_ip)s %(user_email)s-%(session_id)s %(pathname)s:%(funcName)s:%(lineno)d %(message)s")  # NOQA


def colored_log_handler(filename):
    handler = SparseRotatingFileHandler(
        filename,
        'a',  # write mode
        1 * 1024 * 1024,  # max bytes
        10  # number of old logs to keep
    )
    handler.setFormatter(colored_log_formatter)
    return handler


def colored_stdout_handler():
    import sys
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(colored_log_formatter)
    return handler
