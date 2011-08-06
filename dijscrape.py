#!/usr/bin/env python

import os
import cgi
import oauth2 as oauth
from flask import Flask, render_template, abort, request, session, redirect, url_for, flash

# Get config class name based on context
config_class_name = 'Development' if __name__ == '__main__' else 'Production'

# Flask application
app = Flask(__name__)
app.config.from_object('config.%sConfig' % config_class_name)
app.secret_key = app.config['APP_SECRET_KEY']

# TODO: Move this part elsewhere
consumer = oauth.Consumer(app.config['OAUTH_CONSUMER_KEY'], app.config['OAUTH_CONSUMER_SECRET'])
client = oauth.Client(consumer)

# Views
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    resp, content = client.request(app.config['OAUTH_REQUEST_TOKEN_URL'] + '?scope=' + app.config['OAUTH_SCOPE_URL'], "GET")
    if resp['status'] != '200':
        abort(502, 'Invalid response from Google.')
    session['request_token'] = dict(cgi.parse_qsl(content))
    return redirect('%s?oauth_token=%s&oauth_callback=http://%s%s'
        % (app.config['OAUTH_AUTHORIZATION_URL'], session['request_token']['oauth_token'], request.host, url_for('oauth_authorized')))

@app.route('/oauth-scraper')
def oauth_scraper():
    # TODO: Handle email scraping
    return 'Connected!'

# OAuth callbacks
@app.route('/oauth-authorized')
def oauth_authorized():
    token = oauth.Token(session['request_token']['oauth_token'], session['request_token']['oauth_token_secret'])
    client = oauth.Client(consumer, token)
    resp, content = client.request(app.config['OAUTH_ACCESS_TOKEN_URL'], "GET")
    # TODO: Handle 'Deny access' (status 400)
    if resp['status'] != '200':
        raise Exception("Invalid response from Google.")
    access_token = dict(cgi.parse_qsl(content))
    # TODO: Store the access token
    return redirect(url_for('oauth_scraper'))

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
