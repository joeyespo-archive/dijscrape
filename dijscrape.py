#!/usr/bin/env python

import os
from flask import Flask, render_template

# Get config class name based on context
config_class_name = 'Development' if __name__ == '__main__' else 'Production'

# Flask application
app = Flask(__name__)
app.config.from_object('config.%sConfig' % config_class_name)

# Views
@app.route('/')
def index():
    # TODO: Get user and use the home page if logged in
    return render_template('index.html')

# Error handlers
@app.errorhandler(404)
def page_not_found(error = None):
    return render_template('error404.html'), 404

@app.errorhandler(500)
@app.route('/internal_error.html')
def internal_error(error = None):
    return render_template('error500.html'), 500

# Run dev server
if __name__ == '__main__':
    app.run(app.config['DEV_HOST'], port=app.config['DEV_PORT'], debug=app.config['DEBUG'])
