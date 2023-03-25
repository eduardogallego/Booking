import json


class Config:

    def __init__(self):
        with open('config.json', "r") as config_file:
            self._config = json.load(config_file)

    def get(self, parameter):
        return self._config.get(parameter)
