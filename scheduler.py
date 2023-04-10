import logging
import ntplib
import time

from apiclient import ApiClient
from datetime import datetime, timedelta
from threading import Thread
from utils import Config

logger = logging.getLogger('scheduler')
config = Config()
api_client = ApiClient(config)


class Scheduler(Thread):
    def __init__(self, timestamp, court, cache):
        Thread.__init__(self)
        self.event_id = 'unknown'
        self.timestamp = timestamp
        self.court = court
        self.cache = cache

    def run(self):
        self.event_id = self.cache.add_scheduled_event(self.timestamp, self.court)
        now = datetime.now()
        delta = self.timestamp - now - timedelta(hours=24)
        if delta.total_seconds() < 0:
            if now < self.timestamp:  # still in range
                error = api_client.reserve_court(timestamp=self.timestamp, court=self.court)
                if error:
                    logger.error('Court %d %s, Error: %s'
                                 % (self.court, self.timestamp.strftime('%m-%d %H'), error))
                    self.cache.set_scheduled_event_error(self.event_id, error)
                    # TODO ignore scheduled_events with error
                else:
                    # TODO refresh events and delete scheduled_events entry
                    pass
                return
            else:  # event in the past
                error = "Timestamp in the past. Event not booked."
                logger.error('Court %d %s, Error: %s'
                               % (self.court, self.timestamp.strftime('%m-%d %H'), error))
                self.cache.set_scheduled_event_error(self.event_id, error)
                return
        sleep_delta = None
        sleeps = [timedelta(days=1), timedelta(hours=8), timedelta(hours=4), timedelta(hours=1),
                  timedelta(minutes=20), timedelta(minutes=5), timedelta(minutes=1)]
        while self.cache.is_scheduled_event(self.event_id) and delta >= timedelta(minutes=2):
            if sleep_delta:  # second and forth sleeps
                for sleep_delta in sleeps:
                    if delta > sleep_delta + timedelta(minutes=1):
                        break
            else:  # first sleep
                if delta > timedelta(hours=1, minutes=1):
                    sleep_delta = delta % timedelta(hours=1)
                else:
                    sleep_delta = delta % timedelta(minutes=1)
            logger.info('Court %d %s, Delta %s, Sleep %s'
                        % (self.court, self.timestamp.strftime('%Y-%m-%d %H'), delta, sleep_delta))
            time.sleep(sleep_delta.total_seconds())
            delta = self.timestamp - datetime.now() - timedelta(hours=24)

        if not self.cache.is_scheduled_event(self.event_id):
            return

        # Verify credentials
        api_client.check_credentials()

        # NTP Correct timestamp = dest_time + offset
        ntp_client = ntplib.NTPClient()
        ntp_response = ntp_client.request(host='europe.pool.ntp.org', version=3)

        # Launch burst of requests
        requests = []
        for delay_sec in [-0.2, -0.05, 0.05, 0.2, 0.5]:
            request = Request(timestamp=self.timestamp, court=self.court,
                              offset_sec=ntp_response.offset, delay_sec=delay_sec)
            requests.append(request)
            request.start()
        for request in requests:
            request.join()

        # check reservations
        time.sleep(1)
        reservations = []
        for reservation in api_client.get_month_reservations(self.timestamp):
            if self.timestamp == datetime.strptime(reservation['dtFecha'], '%d/%m/%Y %H:%M:%S') \
                    and str(self.court) in reservation.get['tmTitulo']:
                reservations.append(reservation)
        if reservations:
            self.cache.delete_scheduled_event(self.event_id)
        else:
            self.cache.set_scheduled_event_error(self.event_id, requests[-1].error)
        if len(reservations) > 1:
            for i in range(1, len(reservations)):
                api_client.delete_reservation(reservations[i]['idEvento'])


class Request(Thread):
    def __init__(self, timestamp, court, offset_sec, delay_sec):
        Thread.__init__(self)
        self.timestamp = timestamp
        self.court = court
        self.offset_sec = offset_sec
        self.delay_sec = delay_sec
        self.error = None

    def run(self):
        delta = self.timestamp - datetime.now() - timedelta(hours=24, seconds=(self.offset_sec - self.delay_sec))
        if delta.total_seconds() < 0:
            self.error = 'Negative delta'
        else:
            logger.info('Court %d %s, Delta %s, Offset: %s, Delay: %s'
                        % (self.court, self.timestamp.strftime('%Y-%m-%d %H'), delta, self.offset_sec, self.delay_sec))
            time.sleep(delta.total_seconds())
            self.error = api_client.reserve_court(timestamp=self.timestamp, court=self.court)
        logger.info('Court %d %s, Offset: %s, Delay: %s, Error: %s'
                    % (self.court, self.timestamp.strftime('%m-%d %H'), self.offset_sec, self.delay_sec, self.error))
