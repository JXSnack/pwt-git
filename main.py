import copy
import time
from pathlib import Path
import threading

from flask import Flask, g, render_template, request, jsonify

import helper
from helper import Globals

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev"


@app.before_request
def load_user():
    pass


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if not Globals.started:
            return "Game has not started yet"

        if request.form.get("username") in Globals.user_data.keys():
            return render_template("index.html", exists=True, globals=Globals)

        Globals.game_data['connections'] += 1
        Globals.user_data[request.form['username']] = {"last_handshake": helper.millis(), "username": request.form['username']}
        return render_template("game.html", globals=Globals, username=request.form['username'])
    return render_template("index.html", exists=False, globals=Globals)


@app.route("/admin")
def admin():
    return render_template("admin.html", globals=Globals)


@app.route("/start")
def start():
    if request.args.get("key") == Globals.key:
        Globals.started = True
        Globals.game_data["page"] = 0
        Globals.game_data["state"] = 'start'
        Globals.game_data["connections"] = 0
        return "OK"
    return "Invalid permissions"


@app.route("/gamedata")
def gamedata():
    if request.args.get("key") == Globals.key:
        if not Globals.started:
            return "Game has not started yet"

        return jsonify(Globals.game_data)

    return "Invalid permissions"


@app.route('/handshake/<username>')
def handshake(username: str):
    if Globals.user_data.get(username) is None:
        print("Failing handshake for not existing")
        return "User does not exist"

    Globals.user_data[username]['last_handshake'] = helper.millis()
    return jsonify(Globals.user_data[username])


@app.route('/next-page')
def next_state():
    if not Globals.started:
        return "The game has not started yet"

    Globals.game_data['page'] += 1
    Globals.game_data['state'] = "image"
    return "OK"


def disconnect_user(user):
    print("[X] Disconnecting " + user['username'])
    username = user['username']
    Globals.game_data['connections'] -= 1
    del Globals.user_data[username]


def threading_check():
    check_ms = 2000

    while True:
        for user in copy.copy(list(Globals.user_data.keys())):
            if helper.millis() - check_ms > Globals.user_data[user]['last_handshake']:
                disconnect_user(Globals.user_data[user])

        time.sleep(check_ms / 2 / 1000)


if __name__ == "__main__":
    app_thread = threading.Thread(target=lambda: app.run(debug=True, use_reloader=False))
    app_thread.start()

    handshake_thread = threading.Thread(target=lambda: threading_check())
    handshake_thread.start()
