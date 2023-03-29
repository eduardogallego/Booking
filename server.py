import json
import os
import time

from apiclient import ApiClient
from config import Config
from datetime import date
from flask import Flask, render_template, send_from_directory
from security import Security

app = Flask(__name__)
config = Config()

if os.path.isfile(config.get('credentials_file')):
    update_credentials = False
    with open(config.get('credentials_file')) as input_file:
        credentials = json.load(input_file)
        for cookie in credentials['cookies']:
            if time.time() > cookie['expiry']:
                update_credentials = True
                break
else:
    update_credentials = True

if update_credentials:
    security = Security(config)
    while not security.update_credentials():
        print("Error updating the credentials, retry")
    with open(config.get('credentials_file')) as input_file:
        credentials = json.load(input_file)

apiclient = ApiClient(config, credentials)


@app.route('/')
def index():
    day = date.today()
    day_str = day.strftime('%A %-d %B')
    court_status = apiclient.check_court_status(day)
    return render_template("index.html", day=day_str, court_status=court_status)


@app.route('/calendar')
def calendar():
    return render_template("calendar.html")


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'images'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/images/<image>')
def get_image(image):
    return send_from_directory(os.path.join(app.root_path, 'images'), image)


app.run(host='0.0.0.0', port=5000, debug=True)
