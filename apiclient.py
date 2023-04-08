import json
import logging
import os
import requests
import time

from calendar import monthrange
from datetime import datetime, timedelta


class ApiClient:

    def __init__(self, config):
        self.logger = logging.getLogger('api-client')
        self.config = config
        if os.path.isfile(config.get('credentials_file')):
            with open(config.get('credentials_file')) as input_file:
                credentials = json.load(input_file)
            self.token = credentials['token']
            self.token_expiration_date = credentials['token_expiration_date']
        else:
            self.token = None
            self.token_expiration_date = None
        self.headers = {
            'Accept': 'application/json',
            'Authorization': self.token,
            'Content-Type': 'application/json',
            'Host': 'private.tucomunidapp.com',
            'Origin': 'https://private.tucomunidapp.com',
            'Referer': 'https://private.tucomunidapp.com/community/booking-new/18551'
        }

    def login(self):
        user = self.config.get('user_name')
        self.logger.info('Login %s' % user)
        requests_dict = {"Password": self.config.get('user_password'),
                         "User": user, "LoginType": "3", "Invitations": True}
        response = requests.post('https://api.iesa.es/tcsecurity/api/v1/login', json=requests_dict)
        if response.status_code != 200:
            self.logger.error('Error %d - %s' % (response.status_code, response.reason))
            return False
        response_dict = json.loads(response.text)
        self.token = response_dict['Token']
        self.token_expiration_date = response_dict['TokenExpirationDate']
        self.headers['Authorization'] = self.token
        with open(self.config.get('credentials_file'), 'w') as outfile:
            json.dump({'token': self.token, 'token_expiration_date': self.token_expiration_date}, outfile)
        return True

    def _check_credentials(self):
        if not self.token or time.time() > self.token_expiration_date:
            while not self.login():
                time.sleep(1)

    def get_courts_status(self, date):
        date_str = date.strftime('%Y-%m-%d')
        self.logger.info('Get courts status %s' % date_str)
        self._check_credentials()
        request_dict = {'dtReserva': date_str}
        court_dict = {}
        for court_id in [1, 2]:
            request_dict['idElementoComun'] = \
                self.config.get('court1_id') if court_id == 1 else self.config.get('court2_id')
            response = requests.post(self.config.get('court_status_url'), json=request_dict, headers=self.headers)
            if response.status_code != 200:
                self.logger.error('Error court_status %s: %d - %s' % (date_str, response.status_code, response.reason))
                return None
            court_dict[court_id] = json.loads(response.text.encode().decode('utf-8-sig'))
        status_dict = {}
        if len(court_dict) == 2:
            for data in court_dict[1]['data']:
                block = datetime.strptime(data['fromHour'], '%d/%m/%Y %H:%M:%S')  # 25/03/2023 10:00:00
                status_dict[block.strftime('%H')] = {'court1': data['avalaibleCapacity']}
            for data in court_dict[2]['data']:
                block = datetime.strptime(data['fromHour'], '%d/%m/%Y %H:%M:%S')
                status_dict[block.strftime('%H')]['court2'] = data['avalaibleCapacity']
        else:
            self.logger.error("Error court_status %s: court_dict len %d" % (date_str, len(court_dict)))
        return status_dict

    def get_month_reservations(self, date):
        date_str = date.strftime('%Y-%m-%d')
        self.logger.info('Get month reservations: %s' % date_str)
        self._check_credentials()
        ini_day = date.replace(day=1)
        end_day = date.replace(day=monthrange(ini_day.year, ini_day.month)[1])
        request_dict = {"pagination": {"page": 1, "size": 0, "count": 100},
                        "sort": {"sortBy": "dtFecha", "sortOrder": "ASC"},
                        "fechaActivacionDesde": ini_day.strftime('%d/%m/%Y'),   # 01/03/2023
                        "fechaActivacionHasta": end_day.strftime('%d/%m/%Y'),   # 31/03/2023
                        "fechaDiaActual": "", "tmTitulo": "", "lstIdTipoEvento": []}
        response = requests.post(self.config.get('reservations_url'), json=request_dict, headers=self.headers)
        if response.status_code != 200:
            self.logger.error('Error %d - %s' % (response.status_code, response.reason))
            return None
        response_dict = json.loads(response.text.encode().decode('utf-8-sig'))
        return response_dict['data']

    def reserve_court(self, timestamp, court):
        self.logger.info('Reserve court %d: %s' % (court, timestamp.strftime('%Y-%m-%d %H')))
        self._check_credentials()
        booking_end = timestamp + timedelta(hours=1)
        request_dict = {'dtInicioReserva': timestamp.strftime('%Y-%m-%dT%H:%M:%S'),
                        'dtFinReserva': booking_end.strftime('%Y-%m-%dT%H:%M:%S'),
                        'idUsuario': self.config.get('user_id'),
                        'impPrecio': '0', 'idComunidad': '4100059', 'idProperty': '16288528',
                        'numYoungBooking': 0, 'numOldBooking': 0, 'blUserIncluded': '1',
                        'idElementoComun': self.config.get('court1_id') if court == 1 else self.config.get('court2_id')}
        response = requests.post(self.config.get('court_booking_url'), json=request_dict, headers=self.headers)
        if response.status_code != 200:
            self.logger.error('Error %d - %s' % (response.status_code, response.reason))
            return response.reason
        response_dict = json.loads(response.text.encode().decode('utf-8-sig'))
        if response_dict['code'] == 4:
            self.logger.error('Error %d - %s' % (response_dict['code'], response_dict['message']))
            return response_dict['message']
        return None

    def delete_reservation(self, booking_id):
        self.logger.info('Delete reservation %s' % booking_id)
        self._check_credentials()
        url = '%s/%s' % (self.config.get('court_booking_url'), booking_id)
        response = requests.delete(url, headers=self.headers)
        if response.status_code != 200:
            self.logger.error('Error %d - %s' % (response.status_code, response.reason))
            return response.reason
        response_dict = json.loads(response.text.encode().decode('utf-8-sig'))
        if response_dict['code'] == 4:
            self.logger.error('Error %d - %s' % (response_dict['code'], response_dict['message']))
            return response_dict['message']
        return None
