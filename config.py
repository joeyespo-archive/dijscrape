"""\
Config

To add a local configuration, create either config_dev.py or config_prod.py
within this directory. In it, import this module and override any attributes.

For example:
from config import DevelopmentConfig
DevelopmentConfig.DEV_PORT = 80
"""

# TODO: Have attribute markers indicating an override is required and show error in app

class BaseConfig(object):
    ADMINS = ['espo58@gmail.com']
    DEBUG = False
    GMAIL_ERROR_USERNAME = ''
    GMAIL_ERROR_PASSWORD = ''
    OAUTH_REQUEST_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetRequestToken?scope=https://mail.google.com/+https://www.google.com/m8/feeds/'
    OAUTH_AUTHORIZATION_URL = 'https://www.google.com/accounts/OAuthAuthorizeToken'
    OAUTH_ACCESS_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetAccessToken'
    # Override these in your local dev/production config file
    APP_SECRET_KEY = ''
    GOOGLE_KEY = ''
    GOOELE_SECRET = ''

class DevelopmentConfig(BaseConfig):
    DEV_HOST = 'localhost'
    DEV_PORT = 5000
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    APP_SECRET_KEY = 'DEBUG-KEY'

class ProductionConfig(BaseConfig):
    pass

# Import the local configurations, if they exist
try: import config_local
except ImportError: pass

try: import config_prod
except ImportError: pass

try: import config_dev
except ImportError: pass
