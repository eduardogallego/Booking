import json
import requests
import time

from calendar import monthrange
from datetime import datetime


class ApiClient:

    def __init__(self, config, credentials):
        self.config = config
        cookie_header = '; '.join('%s=%s' % (cookie['name'], cookie['value']) for cookie in credentials['cookies'])
        self.headers = {
            'Accept': 'application/json',
            'Authorization': credentials['authorization'],
            'Content-Type': 'application/json',
            'Cookie': cookie_header,
            'Host': 'private.tucomunidapp.com',
            'Origin': 'https://private.tucomunidapp.com',
            'Referer': 'https://private.tucomunidapp.com/community/booking-new/18551'
        }

    def check_court_status(self, date):
        request_dict = {'dtReserva': date.strftime('%Y-%m-%d')}
        court_dict = {}
        for court_id in [1, 2]:
            request_dict['idElementoComun'] = \
                self.config.get('court1_id') if court_id == 1 else self.config.get('court2_id')
            response = requests.post(self.config.get('court_status_url'), json=request_dict, headers=self.headers)
            if response.status_code != 200:
                print('Error %d - %s' % (response.status_code, response.reason))
                return
            court_dict[court_id] = json.loads(response.text.encode().decode('utf-8-sig'))
        status_dict = {}
        for data in court_dict[1]['data']:
            block = datetime.strptime(data['fromHour'], '%d/%m/%Y %H:%M:%S')  # 25/03/2023 10:00:00
            status_dict[block.strftime('%H')] = {'court1': data['avalaibleCapacity']}
        for data in court_dict[2]['data']:
            block = datetime.strptime(data['fromHour'], '%d/%m/%Y %H:%M:%S')
            status_dict[block.strftime('%H')]['court2'] = data['avalaibleCapacity']
        return status_dict

    def get_reservations_in_month(self, date):
        ini_day = date.replace(day=1)
        end_day = date.replace(day=monthrange(ini_day.year, ini_day.month)[1])
        request_dict = {"pagination": {"page": 1, "size": 0, "count": 100},
                        "sort": {"sortBy": "dtFecha", "sortOrder": "ASC"},
                        "fechaActivacionDesde": ini_day.strftime('%d/%m/%Y'),   # 01/03/2023
                        "fechaActivacionHasta": end_day.strftime('%d/%m/%Y'),   # 31/03/2023
                        "fechaDiaActual": "", "tmTitulo": "", "lstIdTipoEvento": []}
        response = requests.post(self.config.get('reservations_url'), json=request_dict, headers=self.headers)
        if response.status_code != 200:
            print('Error %d - %s' % (response.status_code, response.reason))
            return
        response_dict = json.loads(response.text.encode().decode('utf-8-sig'))
        return response_dict['data']

    def reserve_court(self, court=None):
        ini_timestamp = time.time() * 1000
        request_dict = {'dtInicioReserva': '2023-03-25T11:00:00', 'dtFinReserva': '2023-03-25T12:00:00',
                        'impPrecio': '0', 'idUsuario': self.config.get('user_id'), 'idComunidad': '4100059',
                        'idProperty': '16288528', 'numYoungBooking': 0, 'numOldBooking': 0, 'blUserIncluded': '1'}
        for court_id in [1, 2]:
            if court is None or court == court_id:
                request_dict['idElementoComun'] = \
                    self.config.get('court1_id') if court_id == 1 else self.config.get('court2_id')
                response = requests.post(self.config.get('court_booking_url'), json=request_dict, headers=self.headers)
                if response.status_code != 200:
                    print('%d ms: Error %d - %s'
                          % (time.time() * 1000 - ini_timestamp, response.status_code, response.reason))
                    return False
                response_dict = json.loads(response.text.encode().decode('utf-8-sig'))
                print("%d ms: Court %d Reservation %s"
                      % (time.time() * 1000 - ini_timestamp, court_id, response_dict['message']))
        return True
