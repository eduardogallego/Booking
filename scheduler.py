import logging
import ntplib
import time

from apiclient import ApiClient
from datetime import datetime, timedelta
from threading import Thread
from utils import Config


class Scheduler(Thread):
    def __init__(self, timestamp, court):
        Thread.__init__(self)
        self.logger = logging.getLogger('scheduler')
        self.timestamp = timestamp
        self.court = court
        self.config = Config()

    def run(self):
        delta = self.timestamp - datetime.now() - timedelta(hours=24)
        self.logger.info('Court %d %s, Delta: %s' % (self.court, self.timestamp.strftime('%m-%d %H'), delta))
        while delta > timedelta(days=1):
            time.sleep((delta % timedelta(days=1)).total_seconds())
            delta = self.timestamp - datetime.now() - timedelta(hours=24)
            self.logger.info('Court %d %s, Delta: %s' % (self.court, self.timestamp.strftime('%m-%d %H'), delta))
        while delta > timedelta(hours=1):
            time.sleep((delta % timedelta(hours=1)).total_seconds())
            delta = self.timestamp - datetime.now() - timedelta(hours=24)
            self.logger.info('Court %d %s, Delta: %s' % (self.court, self.timestamp.strftime('%m-%d %H'), delta))
        while delta > timedelta(minutes=1):
            time.sleep((delta % timedelta(minutes=1)).total_seconds())
            delta = self.timestamp - datetime.now() - timedelta(hours=24)
            self.logger.info('Court %d %s, Delta: %s' % (self.court, self.timestamp.strftime('%m-%d %H'), delta))
        # NTP Correct timestamp = dest_time + offset
        ntp_client = ntplib.NTPClient()
        ntp_response = ntp_client.request(host='europe.pool.ntp.org', version=3)
        # Launch bunch of requests
        for delay_sec in [-0.1, -0.05, 0, 0.05, 0.1]:
            Request(timestamp=self.timestamp, court=self.court, offset_sec=ntp_response.offset,
                    delay_sec=delay_sec, config=self.config).start()


class Request(Thread):
    def __init__(self, timestamp, court, offset_sec, delay_sec, config):
        Thread.__init__(self)
        self.logger = logging.getLogger('request')
        self.timestamp = timestamp
        self.court = court
        self.offset_sec = offset_sec
        self.delay_sec = delay_sec
        self.api_client = ApiClient(config)

    def run(self):
        time.sleep((self.timestamp - datetime.now()
                    - timedelta(hours=24, seconds=(self.offset_sec - self.delay_sec))).total_seconds())
        error = self.api_client.reserve_court(timestamp=self.timestamp, court=self.court)
        self.logger.info('Try Court %d %s, Now: %s, Offset: %s, Delay: %s, Error: %s'
                         % (self.court, self.timestamp.strftime('%m-%d %H'), datetime.now(),
                            self.offset_sec, self.delay_sec, error))


if __name__ == '__main__':
    date_time = datetime.strptime('2023-04-06T01:35:00', '%Y-%m-%dT%H:%M:%S')
    Scheduler(date_time, 1).start()
