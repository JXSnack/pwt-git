from flask import Flask, g, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
from io import BytesIO
from PIL import Image
import base64
from pathlib import Path

import helper
from helper import Globals

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev"
socketio = SocketIO(app)

Path("instance").mkdir(exist_ok=True, parents=True)


@app.before_request
def load_user():
    pass


@app.route("/", methods=["GET", "POST", "FETCH", "DELETE", "PUT"])
def _index():
    return redirect(url_for("index"))


@app.route("/game", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if not Globals.started:
            return "Game has not started yet"

        if request.form.get("username") in Globals.user_data.keys():
            return render_template("index.html", exists=True, globals=Globals)

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


@socketio.on('next_page')
def next_page():
    if not Globals.started:
        print("[X] Denied next page request, because game has not started yet")
        return

    emit("next_page", broadcast=True)


@socketio.on('connect')
def io_connect():
    is_index = request.headers['Referer'].endswith(url_for("index"))
    if not Globals.started or not is_index:
        print(f"[X] Denied connection. {Globals.started=}@{request.headers['Referer']} ({is_index})")
        return

    if Globals.user_data.get(request.sid) is None:
        Globals.user_data[request.sid] = {}
        Globals.game_data['connections'] += 1
        emit('client_connected', Globals.game_data['connections'], broadcast=True)
        print(f"\033[1;34m[CONNECT] Connected {Globals.game_data['connections']}\033[0m")
    else:
        print("[X] Ignoring connection attempt from already established user")


@socketio.on('identify')
def io_identify(data):
    is_index = request.headers['Referer'].endswith(url_for("index"))
    if not Globals.started or not is_index:
        print(f"[X] Denied identify. {Globals.started=}@{request.headers['Referer']} ({is_index})")
        return

    if Globals.user_data.get(request.sid) is not None:
        Globals.user_data[request.sid] = {"username": data['username']}
        Globals.user_data[data['username']] = request.sid
        print(f"\033[1;34m[IDENTIFY] Identified {data['username']}\033[0m")
    else:
        print("[X] Ignoring identify attempt from a session that has not connected yet")


@socketio.on('disconnect')
def io_disconnect():
    is_index = request.headers['Referer'].endswith(url_for("index"))
    if not Globals.started or not is_index:
        print(f"[X] Denied disconnection. {Globals.started=}@{request.headers['Referer']} ({is_index})")
        return

    if Globals.user_data.get(request.sid) is not None:
        Globals.game_data['connections'] -= 1
        del Globals.user_data[request.sid]
        emit('client_disconnected', Globals.game_data['connections'], broadcast=True)
        print(f"\033[1;34m[DISCONNECT] Disconnecting {Globals.game_data['connections']}\033[0m")
    else:
        print("[X] Ignoring disconnection attempt from non established user")


@app.route("/save_image/<username>", methods=["POST"])
def save_image(username: str):
    data = request.json['image']
    image_data = base64.b64decode(data.split(',')[1])
    image = Image.open(BytesIO(image_data))
    image.save(f'instance/drawing-{username}.png')
    return "Image saved successfully!"


@socketio.on('save_drawing')
def handle_save_drawing(data):
    emit('save_image', data, broadcast=True)


if __name__ == "__main__":
    socketio.run(app, allow_unsafe_werkzeug=True, debug=True)
