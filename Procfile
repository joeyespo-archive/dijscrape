web: env SETTINGS_MODULE=heroku_config.py gunicorn dijscrape:app -k gevent -w 2 -b 0.0.0.0:$PORT
worker: python worker.py
