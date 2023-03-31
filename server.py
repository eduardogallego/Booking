import json
import os
import time

from apiclient import ApiClient
from config import Config
from datetime import date, datetime, timedelta
from flask import Flask, render_template, request, send_from_directory
from security import Security

app = Flask(__name__)
config = Config()
status_cache = {}

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


@app.route('/', methods=['GET'])
def index():
    day = date.today()
    day_str = day.strftime('%A %-d %B')
    court_status = apiclient.check_court_status(day)
    return render_template("index.html", day=day_str, court_status=court_status)


@app.route('/calendar', methods=['GET'])
def calendar():
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')
    return render_template("calendar.html", today=today_str)


@app.route('/events', methods=['GET'])
def events():
    args = request.args
    start = args['start'].split('T', 1)[0]
    start_date = datetime.strptime(start, '%Y-%m-%d')
    end = args['end'].split('T', 1)[0]
    end_date = datetime.strptime(end, '%Y-%m-%d')
    request_date = start_date
    result = []
    now = datetime.now()
    while request_date < end_date:
        if request_date.replace(hour=10) > now + timedelta(days=1):
            break
        request_date_str = request_date.strftime('%Y-%m-%d')
        if request_date_str in status_cache:
            result += status_cache.get(request_date_str)
            request_date += timedelta(days=1)
            continue
        print('Request date: %s' % request_date)
        booked_events = []
        court_status = apiclient.check_court_status(request_date)
        for hour, available in court_status.items():
            for court in ['court1', 'court2']:
                if available[court] == '0':
                    if court == 'court1':
                        event_start = request_date.replace(hour=int(hour))
                        event_end = request_date.replace(hour=int(hour), minute=30)
                    else:   # court2
                        event_start = request_date.replace(hour=int(hour), minute=30)
                        event_end = request_date.replace(hour=int(hour) + 1,)
                    booked_events.append({
                        "start": event_start.strftime('%Y-%m-%dT%H:%M:%S'),
                        "end": event_end.strftime('%Y-%m-%dT%H:%M:%S'),
                        "display": "background", "color": "#ff9f89"})
        if now > request_date.replace(hour=22):
            status_cache[request_date_str] = booked_events
        result += booked_events
        request_date += timedelta(days=1)
    return result


@app.route('/book/<book_timestamp>', methods=['GET'])
def book(book_timestamp):
    return render_template("book.html", date=book_timestamp)


@app.route('/favicon.ico', methods=['GET'])
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'images'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/images/<image>', methods=['GET'])
def get_image(image):
    return send_from_directory(os.path.join(app.root_path, 'images'), image)


app.run(host='0.0.0.0', port=5000, debug=True)
