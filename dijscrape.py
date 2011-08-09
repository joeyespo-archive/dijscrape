#!/usr/bin/env python

import os
import cgi
import oauth2 as oauth
from flask import Flask, render_template, abort, request, session, redirect, url_for, flash
from tasks import scrape_gmail_messages

# Get config class name based on context
config_class_name = 'Development' if __name__ == '__main__' else 'Production'

# Flask application
app = Flask(__name__)
app.config.from_object('config.%sConfig' % config_class_name)
app.secret_key = app.config['APP_SECRET_KEY']
consumer = oauth.Consumer(app.config['GOOGLE_KEY'], app.config['GOOGLE_SECRET'])
client = oauth.Client(consumer)


# Views
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login')
def login():
    email = request.args.get('email')
    if not email:
        flash('Please enter a valid email.')
        return redirect('/')
    resp, content = client.request(app.config['OAUTH_REQUEST_TOKEN_URL'])
    if resp['status'] != '200':
        abort(502, 'Invalid response from Google.')
    session['request_token'] = dict(cgi.parse_qsl(content))
    return redirect('%s?oauth_token=%s&oauth_callback=http://%s%s'
        % (app.config['OAUTH_AUTHORIZATION_URL'], session['request_token']['oauth_token'], request.host, url_for('oauth_authorized', email=email)))


@app.route('/oauth-authorized')
def oauth_authorized():
    email = request.args.get('email')
    token = oauth.Token(session['request_token']['oauth_token'], session['request_token']['oauth_token_secret'])
    client = oauth.Client(consumer, token)
    resp, content = client.request(app.config['OAUTH_ACCESS_TOKEN_URL'])
    # TODO: Handle 'Deny access' (status 400)
    if resp['status'] != '200':
        # TODO: Show better error
        abort(502, 'Invalid response from Google.')
    session['access_token'] = dict(cgi.parse_qsl(content))
    return redirect(url_for('oauth_scraper', email=email))


@app.route('/oauth-scraper')
def oauth_scraper():
    email = request.args.get('email')
    # TODO: Get the email from oauth -- need multiple scopes to do this: http://stackoverflow.com/questions/3128981/require-google-to-return-email-address-as-part-of-oauth
    access_oauth_token, access_oauth_token_secret = session['access_token']['oauth_token'], session['access_token']['oauth_token_secret']
    consumer_key, consumer_secret = app.config['GOOGLE_KEY'], app.config['GOOGLE_SECRET']
    result = scrape_gmail_messages.delay(email, access_oauth_token, access_oauth_token_secret, consumer_key, consumer_secret)
    # TODO: return render_template('processing.html')
    phone_numbers = result.get()
    return render_template('results.html', phone_numbers=phone_numbers)
        

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
