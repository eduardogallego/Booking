import json
import requests
import time

from config import Config
from datetime import date


class ApiClient:

    def __init__(self, credentials):
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

    def check_court_status(self):
        ini_timestamp = time.time() * 1000
        today = date.today()
        request_dict = {'dtReserva': today.strftime('%Y-%m-%d')}
        court_dict = {}
        for court_id in [1, 2]:
            request_dict['idElementoComun'] = Config.court_1_id.value if court_id == 1 else Config.court_2_id.value
            response = requests.post(Config.url_court_status.value, json=request_dict, headers=self.headers)
            if response.status_code != 200:
                print('%d ms: Error %d - %s'
                      % (time.time() * 1000 - ini_timestamp, response.status_code, response.reason))
                return
            court_dict[court_id] = json.loads(response.text.encode().decode('utf-8-sig'))
            print("%d ms: Court %d %s"
                  % (time.time() * 1000 - ini_timestamp, court_id, court_dict[court_id]['message']))
        status_dict = {}
        for data in court_dict[1]['data']:
            status_dict[data['fromHour']] = {'available1': data['avalaibleCapacity']}
        for data in court_dict[1]['data']:
            status_dict[data['fromHour']]['available2'] = data['avalaibleCapacity']
        for fromHour in status_dict:
            status = status_dict[fromHour]
            print('%s, %s, %s' % (fromHour, status['court1'], status['court2']))
        print(status_dict)

    def reserve_court(self, court=None):
        ini_timestamp = time.time() * 1000
        request_dict = {'dtInicioReserva': '2023-03-25T11:00:00', 'dtFinReserva': '2023-03-25T12:00:00',
                        'impPrecio': '0', 'idUsuario': Config.user_id.value, 'idComunidad': '4100059',
                        'idProperty': '16288528', 'numYoungBooking': 0, 'numOldBooking': 0, 'blUserIncluded': '1'}
        for court_id in [1, 2]:
            if court is None or court == court_id:
                request_dict['idElementoComun'] = Config.court_1_id.value if court_id == 1 else Config.court_2_id.value
                response = requests.post(Config.url_court_booking.value, json=request_dict, headers=self.headers)
                if response.status_code != 200:
                    print('%d ms: Error %d - %s'
                          % (time.time() * 1000 - ini_timestamp, response.status_code, response.reason))
                    return
                response_dict = json.loads(response.text.encode().decode('utf-8-sig'))
                print("%d ms: Court %d Reservation %s"
                      % (time.time() * 1000 - ini_timestamp, court_id, response_dict['message']))
