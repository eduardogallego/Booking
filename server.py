from datetime import date
from flask import Flask, render_template

app = Flask(__name__)


@app.route('/')
def index():
    today = date.today()
    day = today.strftime('%Y-%m-%d')
    court_status = {'25/03/2023 10:00:00': {'court1': '1', 'court2': '1'},
                    '25/03/2023 11:00:00': {'court1': '0', 'court2': '0'},
                    '25/03/2023 12:00:00': {'court1': '1', 'court2': '1'},
                    '25/03/2023 13:00:00': {'court1': '0', 'court2': '0'},
                    '25/03/2023 14:00:00': {'court1': '1', 'court2': '1'},
                    '25/03/2023 15:00:00': {'court1': '0', 'court2': '0'},
                    '25/03/2023 16:00:00': {'court1': '1', 'court2': '1'},
                    '25/03/2023 17:00:00': {'court1': '0', 'court2': '0'},
                    '25/03/2023 18:00:00': {'court1': '0', 'court2': '0'},
                    '25/03/2023 19:00:00': {'court1': '1', 'court2': '1'},
                    '25/03/2023 20:00:00': {'court1': '1', 'court2': '1'},
                    '25/03/2023 21:00:00': {'court1': '1', 'court2': '1'}}
    return render_template("index.html", day=day, court_status=court_status)

