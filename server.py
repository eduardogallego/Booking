import logging
import os

from apiclient import ApiClient
from datetime import date, datetime, timedelta
from cache import Cache
from flask import Flask, redirect, render_template, request, send_from_directory
from flask_login import LoginManager, login_required, login_user
from threading import Thread
from scheduler import Scheduler
from utils import Config, Logger, User
from werkzeug import serving

Logger()
serving._log_add_style = False          # disable colors in werkzeug server
logger = logging.getLogger('server')
config = Config()
app = Flask(__name__)
app.secret_key = config.get('secret_key')
api_client = ApiClient(config)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/login"
user = User(config.get('user_id'), config.get('user_name'), config.get('user_password'))
status_cache = {}
events_cache = {}
cache = Cache()


@login_manager.user_loader
def load_user(user_id):
    return user if user.get_id() == user_id else None


@app.route('/login', methods=['GET'])
def login():
    return render_template("login_form.html", error=None)


@app.route('/login_action', methods=['POST'])
def login_action():
    form_user = request.form['user']
    form_password = request.form['password']
    if user.get_user_name() == form_user and user.login(form_password) \
            and login_user(user=user, remember=True, duration=timedelta(days=30)):
        logger.info("User %s authenticated" % form_user)
        return redirect("/calendar")
    else:
        user.logout()
        logger.warning("Authentication error %s %s" % (form_user, form_password))
        return render_template("login_form.html", error="Authentication error: wrong user/pwd")


@app.route('/', methods=['GET'])
@login_required
def index():
    return redirect("/calendar")


@app.route('/calendar', defaults={'booking_date': None}, methods=['GET'])
@app.route('/calendar/<booking_date>', methods=['GET'])
@login_required
def calendar(booking_date):
    if booking_date is None:
        booking_date = date.today().strftime('%Y-%m-%d')
    return render_template("calendar.html", date=booking_date)


class CourtStatus(Thread):
    def __init__(self, court, request_date):
        Thread.__init__(self)
        self.court = court
        self.request_date = request_date
        self.court_status = None

    def run(self):
        self.court_status = api_client.get_court_status(self.court, self.request_date)


@app.route('/events', methods=['GET'])
@login_required
def events():
    args = request.args
    start = args['start'].split('T', 1)[0]
    start_date = datetime.strptime(start, '%Y-%m-%d')
    end = args['end'].split('T', 1)[0]
    end_date = datetime.strptime(end, '%Y-%m-%d')
    request_date = start_date
    result = []
    # court status
    court_status_threads = []
    now = datetime.now()
    while request_date < end_date:
        if request_date.replace(hour=10) > now + timedelta(days=1):
            break
        request_date_str = request_date.strftime('%Y-%m-%d')
        if request_date_str in status_cache:
            result += status_cache.get(request_date_str)
            request_date += timedelta(days=1)
            continue
        court_1_thread = CourtStatus(1, request_date)
        court_1_thread.start()
        court_status_threads.append(court_1_thread)
        court_2_thread = CourtStatus(2, request_date)
        court_2_thread.start()
        court_status_threads.append(court_2_thread)
        request_date += timedelta(days=1)
    for court_status_thread in court_status_threads:
        court_status_thread.join()
        if court_status_thread.court_status is None:
            logger.warning("Court Status %s == None" % court_status_thread.request_date.strftime('%Y-%m-%d'))
            continue
        booked_events = []
        for hour, available in court_status_thread.court_status.items():
            if available == '0':
                if court_status_thread.court == 1:
                    event_start = court_status_thread.request_date.replace(hour=int(hour))
                    event_end = court_status_thread.request_date.replace(hour=int(hour), minute=30)
                    title = '1'
                else:  # court2
                    event_start = court_status_thread.request_date.replace(hour=int(hour), minute=30)
                    event_end = court_status_thread.request_date.replace(hour=int(hour) + 1)
                    title = '2'
                booked_events.append({
                    "start": event_start.strftime('%Y-%m-%dT%H:%M:%S'),
                    "end": event_end.strftime('%Y-%m-%dT%H:%M:%S'),
                    "title": title,
                    "display": "background", "color": "#ff9f89"})
        if now > court_status_thread.request_date.replace(hour=22):
            request_date_str = court_status_thread.request_date.strftime('%Y-%m-%d')
            if request_date_str in status_cache:
                status_cache[request_date_str] += booked_events
            else:
                status_cache[request_date_str] = booked_events
        result += booked_events
    # registered events
    start_month = start_date.replace(day=1)
    request_months = [start_month]
    end_month = (end_date - timedelta(days=1)).replace(day=1)
    if end_month > start_month:
        request_months.append(end_month)
    for month_date in request_months:
        reservations = []
        if cache.is_reservations_in_cache(month_date):
            result += cache.get_reservations(month_date)
        else:
            for reservation in api_client.get_month_reservations(month_date):
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
            cache.add_reservations(month_date, reservations)
            result += reservations
    # future events
    result += cache.get_scheduled_events()
    return result


@app.route('/booking_form/<booking_time>', methods=['GET'])
@login_required
def booking_form(booking_time):
    timestamp = datetime.strptime(booking_time.split('+', 1)[0], '%Y-%m-%dT%H:%M:%S')
    court = 'Court 2' if timestamp.minute == 30 else 'Court 1'
    timestamp = timestamp.replace(minute=0)
    return render_template("booking_form.html", booking_date=timestamp.strftime('%Y-%m-%d'),
                           booking_time=timestamp.strftime('%H:%M'), court=court, error=None)


@app.route('/booking_action', methods=['POST'])
@login_required
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
        court = None  # both courts
    now = datetime.now()

    # schedule future events
    if timestamp > now + timedelta(days=1):
        if court is None:
            Scheduler(timestamp=timestamp, court=1, cache=cache).start()
            Scheduler(timestamp=timestamp, court=2, cache=cache).start()
        else:
            Scheduler(timestamp=timestamp, court=court, cache=cache).start()
        return redirect("/calendar/%s" % timestamp.strftime('%Y-%m-%d'))

    # book events in range
    if timestamp < now:
        error = 'La fecha de la reserva debe ser mayor a la actual'
        return render_template("booking_form.html", booking_date=form_date,
                               booking_time=form_time, court=form_court, error=error)
    else:
        for court_id in [1, 2]:
            if court is None or court == court_id:
                error = api_client.reserve_court(timestamp=timestamp, court=court_id)
                if error:
                    return render_template("booking_form.html", booking_date=form_date,
                                           booking_time=form_time, court=form_court, error=error)
                else:
                    cache.delete_reservations(timestamp)
    return redirect("/calendar/%s" % timestamp.strftime('%Y-%m-%d'))


@app.route('/delete_form/<event_id>', methods=['GET'])
@login_required
def delete_form(event_id):
    event = cache.get_scheduled_event(event_id) if event_id.startswith('fut_') else events_cache[event_id]
    timestamp = datetime.strptime(event['start'], '%Y-%m-%dT%H:%M:%S').replace(minute=0)
    error = event.get('error', None)
    court = 'Court 1' if event['title'] == '1' else 'Court 2'
    return render_template("delete_form.html", booking_date=timestamp.strftime('%Y-%m-%d'),
                           booking_time=timestamp.strftime('%H:%M'), court=court, id=event_id, error=error)


@app.route('/delete_action', methods=['POST'])
@login_required
def delete_action():
    booking_id = request.form['id']
    if booking_id.startswith('fut_'):
        cache.delete_scheduled_event(booking_id)
    else:
        error = api_client.delete_reservation(booking_id=booking_id)
        if error:
            return render_template("delete_form.html", booking=request.form['booking'],
                                   court=request.form['court'], id=request.form['id'], error=error)
        else:
            timestamp = datetime.strptime(request.form['booking_date'], '%Y-%m-%d')
            cache.delete_reservations(timestamp)
    return redirect("/calendar/%s" % request.form['booking_date'])


@app.route('/favicon.ico', methods=['GET'])
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'images'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/images/<image>', methods=['GET'])
def get_image(image):
    return send_from_directory(os.path.join(app.root_path, 'images'), image)


debug_mode = config.get('debug_mode') == 'True'
app.run(host='0.0.0.0', port=config.get('port'), debug=debug_mode)
