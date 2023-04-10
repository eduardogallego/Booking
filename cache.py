import json
import os

from datetime import datetime, timedelta
from utils import Config
from scheduler import Scheduler

config = Config()


class Cache:
    """
    dict: self.scheduled_events
        key = event_id
        value = {"id": event_id, "timestamp": timestamp, "court": court}
        event_id = fut_<timestamp>_<court>
            timestamp: %Y-%m-%dT%H:%M:%S
            court: 1|2
        timestamp = %Y-%m-%d %H
        court = 1|2

    dict: self.reservations
        key =
        value =
    """

    def __init__(self):
        self.reservations = {}
        if os.path.isfile(config.get('scheduled_events_file')):
            with open(config.get('scheduled_events_file')) as input_file:
                self.scheduled_events = json.load(input_file)
        else:
            self.scheduled_events = {}
        for scheduled_event in self.scheduled_events.values():
            timestamp = datetime.strptime(scheduled_event['timestamp'], '%Y-%m-%d %H')
            Scheduler(timestamp, scheduled_event['court'], self).start()

    def _update_scheduled_events_file(self):
        with open(config.get('scheduled_events_file'), 'w') as outfile:
            json.dump(self.scheduled_events, outfile)

    def add_scheduled_event(self, timestamp, court):
        event_id = '%s_%d' % (timestamp.strftime('fut_%Y-%m-%dT%H:%M:%S'), court)
        self.scheduled_events[event_id] = \
            {"id": event_id, "timestamp": timestamp.strftime('%Y-%m-%d %H'), "court": court}
        self._update_scheduled_events_file()
        return event_id

    def delete_scheduled_event(self, event_id):
        self.scheduled_events.pop(event_id)
        self._update_scheduled_events_file()

    def get_scheduled_event(self, event_id):
        scheduled_event = self.scheduled_events.get(event_id)
        timestamp = datetime.strptime(scheduled_event['timestamp'], '%Y-%m-%d %H')
        event_start = timestamp if scheduled_event['court'] == 1 else timestamp + timedelta(minutes=30)
        return {"id": scheduled_event['id'],
                "start": event_start.strftime('%Y-%m-%dT%H:%M:%S'),
                "end": (event_start + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%S'),
                "title": str(scheduled_event['court']),
                "color": "#dc3545" if 'error' in scheduled_event else "#198754"}

    def get_scheduled_events(self):
        events = []
        for scheduled_event in self.scheduled_events.values():
            timestamp = datetime.strptime(scheduled_event['timestamp'], '%Y-%m-%d %H')
            event_start = timestamp if scheduled_event['court'] == 1 else timestamp + timedelta(minutes=30)
            events.append({"id": scheduled_event['id'],
                           "start": event_start.strftime('%Y-%m-%dT%H:%M:%S'),
                           "end": (event_start + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%S'),
                           "title": str(scheduled_event['court']),
                           "color": "#dc3545" if 'error' in scheduled_event else "#198754"})
        return events

    def is_scheduled_event(self, event_id):
        return event_id in self.scheduled_events

    def set_scheduled_event_error(self, event_id, error):
        self.scheduled_events[event_id]['error'] = 'Error: %s' % error
