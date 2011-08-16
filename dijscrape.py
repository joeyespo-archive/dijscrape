#!/usr/bin/env python

import cgi
import oauth2 as oauth
from flask import Flask, render_template, abort, request, session, redirect, url_for, flash
from tasks import scrape_gmail_messages


# Flask application
config_class_name = 'Development' if __name__ == '__main__' else 'Production'
app = Flask(__name__)
app.config.from_object('config.%sConfig' % config_class_name)
app.secret_key = app.config['APP_SECRET_KEY']
if app.config['GMAIL_ERROR_USERNAME']:
    from util import GmailHandler
    app.logger.addHandler(GmailHandler(app.config['GMAIL_ERROR_USERNAME'], app.config['GMAIL_ERROR_PASSWORD'], app.config['ADMINS'], 'DijScrape Failed'))
# Init OAuth
consumer = oauth.Consumer(app.config['GOOGLE_KEY'], app.config['GOOGLE_SECRET'])
client = oauth.Client(consumer)


# Views
@app.route('/')
def index():
    # Check for active task
    return render_template('index.html')


@app.route('/login')
def login():
    # TODO: Check for active task
    resp, content = client.request(app.config['OAUTH_REQUEST_TOKEN_URL'])
    if resp['status'] != '200':
        abort(502, 'Invalid response from Google. Please try again later.')
    session['request_token'] = dict(cgi.parse_qsl(content))
    return redirect('%s?oauth_token=%s&oauth_callback=http://%s%s'
        % (app.config['OAUTH_AUTHORIZATION_URL'], session['request_token']['oauth_token'], request.host, url_for('oauth_authorized')))


@app.route('/oauth-authorized')
def oauth_authorized():
    token = oauth.Token(session['request_token']['oauth_token'], session['request_token']['oauth_token_secret'])
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
    result = scrape_gmail_messages.delay(session['access_token']['oauth_token'], session['access_token']['oauth_token_secret'], app.config['GOOGLE_KEY'], app.config['GOOGLE_SECRET'])
    # Save the task ID and redirect to the processing page
    print 'Task started:', result.task_id
    session['task_id'] = result.task_id
    return redirect(url_for('processing'))


@app.route('/processing')
def processing():
    # Check whether we're still processing in case there's a hard refresh
    task_id = session.get('task_id')
    status = poll_task(task_id)
    if status is None or status == 'True':
        return redirect(url_for('results' if status == 'True' else 'index'))
    # Render the processing page normally
    print 'Processing task:', task_id
    return render_template('processing.html', task_id=task_id)


@app.route('/results')
def results():
    if app.config['DEBUG']:
        phone_numbers = scrape_gmail_messages(session['access_token']['oauth_token'], session['access_token']['oauth_token_secret'], app.config['GOOGLE_KEY'], app.config['GOOGLE_SECRET'])
        return render_template('results.html', phone_numbers=phone_numbers)
    # Check for completion
    task_id = session.get('task_id')
    status = poll_task(task_id)
    if status != 'True':
        return redirect(url_for('processing' if status == 'False' else 'index'))
    print 'Task complete:', task_id
    # Show results
    result = scrape_gmail_messages.AsyncResult(task_id)
    phone_numbers = result.result
    return render_template('results.html', phone_numbers=phone_numbers)


@app.route('/poll-task/<task_id>')
def poll_task(task_id):
    # Check whether the task is still processing and return True if complete, False if still processing, a string for progress, or None if not found
    print 'Polled task:', task_id
    if app.config['DEBUG']:
        return 'True'
    try:
        result = scrape_gmail_messages.AsyncResult(task_id)
        return str(result.ready())
    except:
        print 'No task:', task_id
        return 'None'


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


# Run dev server
if __name__ == '__main__':
    app.run(app.config['DEV_HOST'], port=app.config['DEV_PORT'], debug=app.config['DEBUG'])
