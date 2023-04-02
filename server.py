import os

from apiclient import ApiClient
from config import Config
from datetime import date, datetime, timedelta
from flask import Flask, redirect, render_template, request, send_from_directory

app = Flask(__name__)
config = Config()
apiclient = ApiClient(config)
status_cache = {}
reservations_cache = {}
events_cache = {}


@app.route('/', methods=['GET'])
def index():
    day = date.today()
    day_str = day.strftime('%A %-d %B')
    court_status = apiclient.get_courts_status(day)
    return render_template("index.html", day=day_str, court_status=court_status)


@app.route('/calendar', defaults={'booking_date': None}, methods=['GET'])
@app.route('/calendar/<booking_date>', methods=['GET'])
def calendar(booking_date):
    if booking_date is None:
        booking_date = date.today().strftime('%Y-%m-%d')
    return render_template("calendar.html", date=booking_date)


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
        booked_events = []
        court_status = apiclient.get_courts_status(request_date)
        for hour, available in court_status.items():
            for court in ['court1', 'court2']:
                if available[court] == '0':
                    if court == 'court1':
                        event_start = request_date.replace(hour=int(hour))
                        event_end = request_date.replace(hour=int(hour), minute=30)
                        title = '1'
                    else:   # court2
                        event_start = request_date.replace(hour=int(hour), minute=30)
                        event_end = request_date.replace(hour=int(hour) + 1,)
                        title = '2'
                    booked_events.append({
                        "start": event_start.strftime('%Y-%m-%dT%H:%M:%S'),
                        "end": event_end.strftime('%Y-%m-%dT%H:%M:%S'),
                        "title": title,
                        "display": "background", "color": "#ff9f89"})
        if now > request_date.replace(hour=22):
            status_cache[request_date_str] = booked_events
        result += booked_events
        request_date += timedelta(days=1)

    start_month = start_date.replace(day=1)
    request_months = [start_month]
    end_month = (end_date - timedelta(days=1)).replace(day=1)
    if end_month > start_month:
        request_months.append(end_month)
    for month_date in request_months:
        reservations = []
        reservations_month = month_date.strftime('%Y-%m')
        if reservations_month in reservations_cache:
            result += reservations_cache.get(reservations_month)
        else:
            for reservation in apiclient.get_month_reservations(month_date):
                event_start = datetime.strptime(reservation['dtFecha'], '%d/%m/%Y %H:%M:%S')
                court_1 = 'Nº1' in reservation['tmTitulo']
                if not court_1:
                    event_start += timedelta(minutes=30)
                event_end = event_start + timedelta(minutes=30)
                title = '1' if court_1 else '2'
                event = {
                    "id": str(reservation['idEvento']),
                    "start": event_start.strftime('%Y-%m-%dT%H:%M:%S'),
                    "end": event_end.strftime('%Y-%m-%dT%H:%M:%S'),
                    "title": title}
                reservations.append(event)
                events_cache[event['id']] = event
            reservations_cache[reservations_month] = reservations
            result += reservations
    return result


@app.route('/booking_form/<booking_time>', methods=['GET'])
def booking_form(booking_time):
    timestamp = datetime.strptime(booking_time.split('+', 1)[0], '%Y-%m-%dT%H:%M:%S')
    court = 'Court 2' if timestamp.minute == 30 else 'Court 1'
    timestamp = timestamp.replace(minute=0)
    return render_template("booking_form.html", booking_date=timestamp.strftime('%Y-%m-%d'),
                           booking_time=timestamp.strftime('%H:%M'), court=court, error=None)


@app.route('/event_form/<event_id>', methods=['GET'])
def event_form(event_id):
    event = events_cache[event_id]
    event_start = datetime.strptime(event['start'], '%Y-%m-%dT%H:%M:%S')
    court = 'Court 1' if event['title'] == '1' else 'Court 2'
    return render_template("event_form.html", booking=event_start.strftime('%d/%m/%Y %H:%M:%S'),
                           court=court, id=event_id, error=None)


@app.route('/booking_action', methods=['POST'])
def booking_action():
    form_date = request.form['booking_date']
    form_time = request.form['booking_time']
    form_datetime = '%s %s' % (form_date, form_time)
    timestamp = datetime.strptime(form_datetime, '%Y-%m-%d %H:%M')
    form_court = request.form['court']
    if form_court == 'Court 1':
        court = 1
    elif form_court == 'Court 2':
        court = 2
    else:
        court = None
    error = apiclient.reserve_court(timestamp=timestamp, court=court)
    if error:
        return render_template("booking_form.html", booking_date=form_date,
                               booking_time=form_time, court=form_court, error=error)
    else:
        reservations_cache.pop(timestamp.strftime('%Y-%m'))
        return redirect("calendar/%s" % timestamp.strftime('%Y-%m-%d'))


@app.route('/delete_action', methods=['POST'])
def delete_action():
    error = apiclient.delete_reservation(booking_id=request.form['id'])
    if error:
        return render_template("event_form.html", booking=request.form['booking'],
                               court=request.form['court'], id=request.form['id'], error=error)
    else:
        timestamp = datetime.strptime(request.form['booking'], '%d/%m/%Y %H:%M:%S')
        reservations_cache.pop(timestamp.strftime('%Y-%m'))
        return redirect("calendar/%s" % timestamp.strftime('%Y-%m-%d'))


@app.route('/favicon.ico', methods=['GET'])
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'images'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/images/<image>', methods=['GET'])
def get_image(image):
    return send_from_directory(os.path.join(app.root_path, 'images'), image)


app.run(host='0.0.0.0', port=config.get('port'), debug=True)
