import json
import logging
import ntplib
import os
import time

from apiclient import ApiClient
from datetime import datetime, timedelta
from threading import Lock, Thread
from utils import Config

logger = logging.getLogger('scheduler')


class FutureEvents:
    def __init__(self):
        self.config = Config()
        if os.path.isfile(self.config.get('future_events_file')):
            with open(self.config.get('future_events_file')) as input_file:
                self.future_events = json.load(input_file)
        else:
            self.future_events = {}
        for future_event in self.future_events.values():
            timestamp = datetime.strptime(future_event['timestamp'], '%Y-%m-%d %H')
            Scheduler(timestamp, future_event['court'], self.config, self).start()

    def _update_future_events_file(self):
        with open(self.config.get('future_events_file'), 'w') as outfile:
            json.dump(self.future_events, outfile)

    def add_future_event(self, timestamp, court):
        event_id = '%s_%d' % (timestamp.strftime('fut_%Y-%m-%dT%H:%M:%S'), court)
        self.future_events[event_id] = {"id": event_id, "timestamp": timestamp.strftime('%Y-%m-%d %H'), "court": court}
        self._update_future_events_file()
        return event_id

    def delete_event(self, event_id):
        self.future_events.pop(event_id)
        self._update_future_events_file()

    def get_event(self, event_id):
        future_event = self.future_events.get(event_id)
        timestamp = datetime.strptime(future_event['timestamp'], '%Y-%m-%d %H')
        event_start = timestamp if future_event['court'] == 1 else timestamp + timedelta(minutes=30)
        return {"id": future_event['id'],
                "start": event_start.strftime('%Y-%m-%dT%H:%M:%S'),
                "end": (event_start + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%S'),
                "title": str(future_event['court']), "color": "#198754"}

    def get_events(self):
        events = []
        for future_event in self.future_events.values():
            timestamp = datetime.strptime(future_event['timestamp'], '%Y-%m-%d %H')
            event_start = timestamp if future_event['court'] == 1 else timestamp + timedelta(minutes=30)
            events.append({"id": future_event['id'],
                           "start": event_start.strftime('%Y-%m-%dT%H:%M:%S'),
                           "end": (event_start + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%S'),
                           "title": str(future_event['court']), "color": "#198754"})
        return events

    def is_future_event(self, event_id):
        return event_id in self.future_events


class Scheduler(Thread):
    def __init__(self, timestamp, court, config, future_events):
        Thread.__init__(self)
        self.event_id = 'unknown'
        self.timestamp = timestamp
        self.court = court
        self.config = config
        self.future_events = future_events

    def run(self):
        if datetime.now() > self.timestamp:
            logger.warning('Court %d %s, Status: Event not booked' % (self.court, self.timestamp.strftime('%m-%d %H')))
            return
        self.event_id = self.future_events.add_future_event(self.timestamp, self.court)
        delta = self.timestamp - datetime.now() - timedelta(hours=24)
        logger.info('Court %d %s, Delta: %s' % (self.court, self.timestamp.strftime('%m-%d %H'), delta))
        while self.future_events.is_future_event(self.event_id) and delta > timedelta(days=1):
            time.sleep((delta % timedelta(days=1)).total_seconds())
            delta = self.timestamp - datetime.now() - timedelta(hours=24)
            logger.info('Court %d %s, Delta: %s' % (self.court, self.timestamp.strftime('%m-%d %H'), delta))
        while self.future_events.is_future_event(self.event_id) and delta > timedelta(hours=1):
            time.sleep((delta % timedelta(hours=1)).total_seconds())
            delta = self.timestamp - datetime.now() - timedelta(hours=24)
            logger.info('Court %d %s, Delta: %s' % (self.court, self.timestamp.strftime('%m-%d %H'), delta))
        while self.future_events.is_future_event(self.event_id) and delta > timedelta(minutes=1):
            time.sleep((delta % timedelta(minutes=1)).total_seconds())
            delta = self.timestamp - datetime.now() - timedelta(hours=24)
            logger.info('Court %d %s, Delta: %s' % (self.court, self.timestamp.strftime('%m-%d %H'), delta))
        if self.future_events.is_future_event(self.event_id):
            # NTP Correct timestamp = dest_time + offset
            ntp_client = ntplib.NTPClient()
            ntp_response = ntp_client.request(host='europe.pool.ntp.org', version=3)
            # Launch burst of requests
            status = Status()
            threads = []
            for delay_sec in [-0.2, -0.05, 0.05, 0.2, 0.5, 1]:
                thread = Request(timestamp=self.timestamp, court=self.court, offset_sec=ntp_response.offset,
                                 delay_sec=delay_sec, status=status, config=self.config)
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join()
            logger.info('Court %d %s, Status: %s %s'
                        % (self.court, self.timestamp.strftime('%m-%d %H'), str(status.finished), ', '.join(status.errors)))


class Status:
    def __init__(self):
        self.finished = False
        self.errors = []
        self.lock = Lock()

    def set_error(self, error):
        with self.lock:
            if error is None:
                self.finished = True
            if error:
                self.errors.append(error)

    def is_finished(self):
        with self.lock:
            return self.finished


class Request(Thread):
    def __init__(self, timestamp, court, offset_sec, delay_sec, status, config):
        Thread.__init__(self)
        self.timestamp = timestamp
        self.court = court
        self.offset_sec = offset_sec
        self.delay_sec = delay_sec
        self.status = status
        self.api_client = ApiClient(config)

    def run(self):
        '''time.sleep((self.timestamp - datetime.now()
                    - timedelta(hours=24, seconds=(self.offset_sec - self.delay_sec))).total_seconds())'''
        if self.status.finished:
            error = 'Scheduler already finished'
        else:
            error = self.api_client.reserve_court(timestamp=self.timestamp, court=self.court)
        self.status.set_error(error)
        logger.info('Try Court %d %s, Now: %s, Offset: %s, Delay: %s, Error: %s'
                    % (self.court, self.timestamp.strftime('%m-%d %H'), datetime.now(),
                       self.offset_sec, self.delay_sec, error))
