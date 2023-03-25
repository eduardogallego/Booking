import json
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from seleniumwire import webdriver


class Security:

    def __init__(self, config):
        self.config = config

    def update_credentials(self):
        ini_timestamp = time.time() * 1000
        driver = None
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
            print("%d ms: Web Driver" % (time.time() * 1000 - ini_timestamp))
            driver.get(self.config.get('login_url'))

            user_input = WebDriverWait(driver, 30).until(
                expected_conditions.presence_of_element_located((By.NAME, 'ion-input-0')))
            print("%d ms: Login Page" % (time.time() * 1000 - ini_timestamp))
            user_input.send_keys(self.config.get('login_user'))
            user_input.send_keys(Keys.RETURN)
            password_input = driver.find_element(By.NAME, 'ion-input-1')
            password_input.send_keys(self.config.get('login_password'))
            password_input.send_keys(Keys.RETURN)

            WebDriverWait(driver, 60).until(
                expected_conditions.presence_of_element_located((By.CLASS_NAME, 'common-zones')))
            print("%d ms: Logged In" % (time.time() * 1000 - ini_timestamp))

            cookies = driver.get_cookies()
            for cookie in cookies:
                print("%d ms: Cookie %s" % ((time.time() * 1000 - ini_timestamp), cookie))

            authorization = None
            for request in driver.requests:
                if request.url.endswith(self.config.get('user_id')):
                    for header in str(request.headers).splitlines():
                        if 'Authorization' in header:
                            authorization = header.split(': ')[1]
            print("%d ms: Authorization %s" % ((time.time() * 1000 - ini_timestamp), authorization))
            credentials = {'cookies': cookies, 'authorization': authorization}
            with open(self.config.get('credentials_file'), 'w') as outfile:
                json.dump(credentials, outfile)
            return True

        except Exception as e:
            print("%d ms: Exception %s" % ((time.time() * 1000 - ini_timestamp), str(e)))
            return False

        finally:
            if driver is not None:
                driver.quit()
