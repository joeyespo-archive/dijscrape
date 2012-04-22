"""\
Default Config

Do NOT change the values here.
Override them in the instance/application_config.py file instead.
"""


# Development settings
DEBUG = None
HOST = 'localhost'
PORT = 5000

# Admin settings
ADMINS = []

# Logging defaults
LOGGING = {
    'version': 1,
    'handlers': { 'console': { 'level': 'DEBUG', 'class': 'logging.StreamHandler', } },
    'loggers': { None: { 'handlers': ['console'], 'level': 'DEBUG', } }
}

# Security settings
SECRET_KEY = None

# Email settings
APP_EMAIL_INFO = None       # Format: ((HOST, PORT), (EMAIL_USER, EMAIL_PASS), FROM_ADDRESS)
ERROR_EMAIL_INFO = None     # Format: ((HOST, PORT), (EMAIL_USER, EMAIL_PASS), FROM_ADDRESS)

# User feedback settings
ANALYTICS_SCRIPT = None
FEEDBACK_BLOCK = None

# OAuth settings
OAUTH_REQUEST_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetRequestToken?scope=https://mail.google.com/+https://www.google.com/m8/feeds/'
OAUTH_AUTHORIZATION_URL = 'https://www.google.com/accounts/OAuthAuthorizeToken'
OAUTH_ACCESS_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetAccessToken'
OAUTH_GMAIL_KEY = ''
OAUTH_GMAIL_SECRET = ''

# Scraper settings
MAILBOX_TO_SCRAPE = '[Gmail]/All Mail'
