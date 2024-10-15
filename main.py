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


if __name__ == "__main__":
    app.run(debug=True)
