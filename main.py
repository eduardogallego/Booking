import json
import os.path
import time

from apiclient import ApiClient
from config import Config
from security import Security

if os.path.isfile(Config.file_credentials.value):
    update_credentials = False
    with open(Config.file_credentials.value) as input_file:
        credentials = json.load(input_file)
        for cookie in credentials['cookies']:
            if time.time() > cookie['expiry']:
                update_credentials = True
                break
else:
    update_credentials = True

if update_credentials:
    security = Security()
    while not security.update_credentials():
        print("Error updating the credentials, retry")
    with open(Config.file_credentials.value) as input_file:
        credentials = json.load(input_file)

apiclient = ApiClient(credentials)
print('\n===========================================================\n')
apiclient.check_court_status()
print('\n===========================================================\n')
# apiclient.reserve_court()
