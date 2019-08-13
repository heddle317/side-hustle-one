from app import app

from flask_assets import Bundle
from flask_assets import Environment


assets = Environment(app)

base_css = Bundle('css/external/bootstrap.min.css',
                  'css/external/bootstrap-theme.min.css',
                  'css/external/bootstrap-social.css',
                  'css/external/font-awesome.min.css',
                  'css/external/sb-admin-2.css',
                  'css/external/docker-icon/fontcustom.css',
                  'css/internal/global.css',
                  filters='cssmin', output='gen/base.%(version)s.css')

assets.register('base_css', base_css)

filters = 'jsmin'

base_js = Bundle('js/internal/angular_app_module.js',
                 filters=filters, output='gen/base.%(version)s.js')

external_js = Bundle('js/external/jquery-1.11.1.min.js',
                     'js/external/bootstrap.min.js',
                     'js/external/angular-file-upload-shim.js',
                     'js/external/angular.js',
                     'js/external/angular-file-upload.js',
                     'js/external/angular-cookies.js',
                     'js/external/angular-resource.js',
                     'js/external/angular-sanitize.js',
                     filters=filters, output='gen/external.%(version)s.js')

assets.register('base_js', base_js)
assets.register('external_js', external_js)