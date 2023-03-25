import json
import os.path
import time

from apiclient import ApiClient
from config import Config
from security import Security

config = Config()

if os.path.isfile(config.get('credentials_file')):
    update_credentials = False
    with open(config.get('credentials_file')) as input_file:
        credentials = json.load(input_file)
        for cookie in credentials['cookies']:
            if time.time() > cookie['expiry']:
                update_credentials = True
                break
else:
    update_credentials = True

if update_credentials:
    security = Security(config)
    while not security.update_credentials():
        print("Error updating the credentials, retry")
    with open(config.get('credentials_file')) as input_file:
        credentials = json.load(input_file)

apiclient = ApiClient(config, credentials)
print('\n===========================================================\n')
print(apiclient.check_court_status())
print('\n===========================================================\n')
# print(apiclient.reserve_court())
