"""\
Config

To add a local configuration, create a file named local_config.py within this
directory. In it, import this module and set the apporipriate class properties.

For example:
from config import DevelopmentConfig
DevelopmentConfig.DEV_PORT = 80
"""

class BaseConfig(object):
    ADMINS = ['espo58@gmail.com']
    DATABASE_URI = 'sqlite://:memory:'
    DEBUG = False

class DevelopmentConfig(BaseConfig):
    DEV_HOST = 'localhost'
    DEV_PORT = 5000
    DEBUG = True

class ProductionConfig(BaseConfig):
    DATABASE_URI = 'mysql://dijscrape@localhost/dijscrape'

# Try importing the local configuration
try:
    import local_config
except:
    pass
