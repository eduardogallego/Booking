from apiclient import ApiClient
from config import Config
from datetime import date

config = Config()
apiclient = ApiClient(config)
today = date.today()
print('\n===========================================================\n')
print(apiclient.get_courts_status(today))
print('\n===========================================================\n')
print(apiclient.get_month_reservations(today))
print('\n===========================================================\n')
# print(apiclient.reserve_court())
