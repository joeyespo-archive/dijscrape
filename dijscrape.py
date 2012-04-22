"""\
Dijscrape
"""

import cgi
import json
import oauth2 as oauth
from logging import error, info
from logging.config import dictConfig
from flask import Flask, render_template, abort, request, session, redirect, url_for, flash
from tasks import scrape_gmail_messages
from helper import email_errors

__version__ = '0.2'


# Flask application
app = Flask(__name__, instance_relative_config=True)
app.config.from_object('default_config')
app.config.from_envvar('SETTINGS_MODULE', silent=True)
if __name__ == '__main__':
    app.config.from_pyfile('dev_config.py', silent=True)
if 'LOGGING' in app.config:
    dictConfig(app.config['LOGGING'])
email_errors(app)
# Init OAuth
consumer = oauth.Consumer(app.config['OAUTH_GMAIL_KEY'], app.config['OAUTH_GMAIL_SECRET'])
client = oauth.Client(consumer)


# Views
@app.route('/')
def index():
    task, ready = get_task_status()
    if task is not None:
        return redirect(url_for('results' if ready else 'processing'))
    return render_template('index.html')


@app.route('/login')
def login():
    task, ready = get_task_status()
    if task is not None:
        return redirect(url_for('results' if ready else 'processing'))
    resp, content = client.request(app.config['OAUTH_REQUEST_TOKEN_URL'])
    if resp['status'] != '200':
        abort(502, 'Invalid response from Google. Please try again later.')
    session['request_token'] = dict(cgi.parse_qsl(content))
    return redirect('%s?oauth_token=%s&oauth_callback=http://%s%s'
        % (app.config['OAUTH_AUTHORIZATION_URL'], session['request_token']['oauth_token'], request.host, url_for('oauth_authorized')))


@app.route('/oauth-authorized')
def oauth_authorized():
    request_token = session.pop('request_token', None)
    if not request_token:
        return redirect(url_for('index'))
    token = oauth.Token(request_token['oauth_token'], request_token['oauth_token_secret'])
    client = oauth.Client(consumer, token)
    resp, content = client.request(app.config['OAUTH_ACCESS_TOKEN_URL'])
    # TODO: Handle 'Deny access' (status 400)
    if resp['status'] != '200':
        abort(502, 'Invalid response from Google. Please try again later.')
    session['access_token'] = dict(cgi.parse_qsl(content))
    # Skip to results when debugging
    if app.config['DEBUG']:
        return redirect(url_for('results'))
    # Start the task with the oauth and google keys
    result = scrape_gmail_messages.delay(app.config['DEBUG'], app.config['MAILBOX_TO_SCRAPE'], session['access_token']['oauth_token'], session['access_token']['oauth_token_secret'], app.config['OAUTH_GMAIL_KEY'], app.config['OAUTH_GMAIL_SECRET'], app.config['APP_EMAIL_INFO'], app.config['ERROR_EMAIL_INFO'], app.config['ADMINS'])
    # Save the task ID and redirect to the processing page
    print 'Task started:', result.task_id
    session['task_id'] = result.task_id
    return redirect(url_for('processing'))


@app.route('/processing')
def processing():
    task, ready = get_task_status()
    if task is None:
        return redirect(url_for('index'))
    elif ready:
        return redirect(url_for('results'))
    print 'Processing task:', task.task_id
    return render_template('processing.html')


@app.route('/results')
def results():
    if app.config['DEBUG']:
        if not session.get('access_token', None):
            return redirect(url_for('index'))
        phone_numbers = scrape_gmail_messages(app.config['DEBUG'], app.config['MAILBOX_TO_SCRAPE'], session['access_token']['oauth_token'], session['access_token']['oauth_token_secret'], app.config['OAUTH_GMAIL_KEY'], app.config['OAUTH_GMAIL_SECRET'], app.config['APP_EMAIL_INFO'], app.config['ERROR_EMAIL_INFO'], app.config['ADMINS'])
        return render_template('results.html', phone_numbers=phone_numbers)
    task, ready = get_task_status()
    if task is None:
        return redirect(url_for('index'))
    elif not ready:
        return redirect(url_for('processing'))
    return render_template('results.html', phone_numbers=task.result)


@app.route('/poll-task')
def poll_task():
    task, ready = get_task_status()
    if not task:
        return json.dumps(None)
    elif ready:
        return json.dumps(True)
    return json.dumps('%s of %s' % task.state if task.state and len(task.state) == 2 else 'unknown progress')


@app.route('/reset')
def reset():
    session.pop('task_id', None)
    session.pop('request_token', None)
    session.pop('access_token', None)
    return redirect(url_for('index'))


@app.route('/performance')
def performance():
    try:
        from bundle_config import config
    except:
        return 'Nothing to report.'
    try:
        if 'postgres' not in config:
            return 'Error: Expected bundle_config.config to include postgres settings but they are missing.'
        import psycopg2
        conn = psycopg2.connect(host = config['postgres']['host'], port = int(config['postgres']['port']), user = config['postgres']['username'], password = config['postgres']['password'], database = config['postgres']['database'])
        cur = conn.cursor()
        cur.execute('SELECT * FROM processed;')
        entries = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('performance.html', entries=entries)
    except:
        from traceback import format_exc
        return 'Error: could not get performance log.\n\n' + str(format_exc())
        

# Error handlers
@app.errorhandler(404)
def page_not_found(message = None):
    return render_template('error404.html'), 404


@app.errorhandler(500)
@app.route('/internal_error.html')
def internal_error(message = None):
    return render_template('error500.html'), 500


# Helper methods
def get_task_status(task_id = None):
    if task_id is None:
        task_id = session.get('task_id', None)
    if not task_id:
        return None, None
    print 'Polled task:', task_id
    if app.config['DEBUG']:
        return 'debug-task', True
    try:
        task = scrape_gmail_messages.AsyncResult(task_id)
        return task, task.ready()
    except:
        print 'No task:', task_id
        return None, None


# Run dev server
if __name__ == '__main__':
    app.run(app.config['HOST'], app.config['PORT'], app.debug != False)
