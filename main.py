import re
import shutil

from flask import Flask, g, render_template, request, jsonify, redirect, url_for, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from io import BytesIO
from PIL import Image
import base64
from pathlib import Path

import helper
from helper import Globals

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev"
CORS(app)
socketio = SocketIO(
    app,
    async_mode='eventlet',
#    logger=True,
#    engineio_logger=True,
    cors_allowed_origins=["https://pwt.snackbag.net", "http://127.0.0.1:5000"]
)

instance_path = Path("instance")
if instance_path.exists():
    shutil.rmtree(instance_path)
instance_path.mkdir(exist_ok=True, parents=True)


@app.before_request
def load_user():
    pass


@app.route("/", methods=["GET", "POST", "FETCH", "DELETE", "PUT"])
def _index():
    return redirect(url_for("index"))


@app.route("/game", methods=["GET", "POST"])
def index():
    if request.args.get('t') == 'k':
        return render_template("kicked.html", globals=Globals)

    if Globals.actually_started:
        return render_template("already_begun.html")

    if request.method == "POST":
        if not Globals.started:
            return "Game has not started yet"

        username = request.form.get("username")
        username = ' '.join(username.split())

        if not re.compile("^([a-zA-Z0-9_\\- :()])*$").match(username):
            return render_template("index.html", illegal=True, exists=False, globals=Globals)

        if helper.check_dict_case_insensitive(Globals.user_data, username):
            return render_template("index.html", exists=True, illegal=False, globals=Globals)

        Globals.user_data[username] = {"type": "user", "username": username}
        return render_template("game.html", globals=Globals, username=username)
    return render_template("index.html", exists=False, illegal=False, globals=Globals)


@app.route("/admin")
def admin():
    return render_template("admin.html", globals=Globals)


@app.route("/monitor")
def monitor():
    return render_template("monitor.html", globals=Globals)


@socketio.on("kick")
def io_kick(username):
    print("\033[1;31m[X] KICKED " + username + "\033[0m")
    emit("kick_user", username, broadcast=True)


@app.route("/start")
def start():
    if request.args.get("key") == Globals.key:
        Globals.started = True
        Globals.game_data["page"] = 0
        Globals.game_data["round"] = 0
        Globals.game_data["state"] = 'start'
        Globals.game_data["ratings"] = {}
        Globals.game_data["connections"] = 0
        Globals.game_data["usernames"] = []
        return "OK"
    return "Invalid permissions"


@app.route("/gamedata")
def gamedata():
    if request.args.get("key") == Globals.key:
        if not Globals.started:
            return "Game has not started yet"

        return jsonify(Globals.game_data)

    return "Invalid permissions"


@socketio.on('set_page')
def set_page(page):
    if not Globals.started:
        print("[X] Denied set page request, because game has not started yet")
        return

    emit("set_page", page, broadcast=True)


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
        Globals.user_data[request.sid] = {"type": "sid_mapping", "username": data['username']}
        Globals.user_data[data['username']]["sid"] = request.sid
        Globals.game_data["ratings"][data['username']] = {}
        Globals.game_data["ratings"][data['username']]["fav"] = 0
        Globals.game_data["ratings"][data['username']]["admin"] = 0
        if data['username'] not in Globals.game_data['usernames']:
            Globals.game_data['usernames'].append(data['username'])

        emit('identify', {'sid': request.sid, 'username': data['username']}, broadcast=True)
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
        username = Globals.user_data[request.sid]['username']
        Globals.game_data['usernames'].remove(username)
        del Globals.user_data[Globals.user_data[request.sid]['username']]
        del Globals.user_data[request.sid]
        del Globals.game_data["ratings"][username]
        emit('client_disconnected', {"amount": Globals.game_data['connections'], "username": username}, broadcast=True)
        print(f"\033[1;34m[DISCONNECT] Disconnecting {Globals.game_data['connections']}\033[0m")
    else:
        print("[X] Ignoring disconnection attempt from non established user")


@socketio.on('request_drawing')
def io_request_drawing():
    emit("request_drawing", broadcast=True)


@socketio.on("request_drawings")
def drawings():
    users_with_drawings = []

    for user in Globals.user_data.keys():
        if Globals.user_data[user]["type"] != "user":
            continue

        if Path(f"instance/{Globals.game_data['round']}/{user}.png").exists():
            users_with_drawings.append(user)

    emit("rating_data", {"users": users_with_drawings}, broadcast=True)


@app.route("/save_image/<username>", methods=["POST"])
def save_image(username: str):
    Path(f"instance/{Globals.game_data['round']}").mkdir(parents=True, exist_ok=True)
    data = request.json['image']
    image_data = base64.b64decode(data.split(',')[1])
    image = Image.open(BytesIO(image_data))
    image.save(f"instance/{Globals.game_data['round']}/{username}.png")
    return "Image saved successfully!"


@app.route("/submit_rating/<username>")
def submit_rating(username: str):
    if Globals.game_data["ratings"].get(username) is None:
        return "Invalid user"

    Globals.game_data['ratings'][username]['fav'] += 1
    print(f"\033[1;32mGot rating for {username}\033[0m")
    return "OK"


@app.route("/next_round")
def next_round():
    if not Globals.started:
        return "Game has not yet started"

    Globals.actually_started = True
    Globals.game_data["round"] += 1
    return "OK"


@app.route("/drawing/<username>")
def drawing(username: str):
    if not Globals.started:
        return "Game has not yet started"

    path = Path(f"instance/{Globals.game_data['round']}/{username}.png")
    if not path.exists():
        return "User has no drawing for this round"

    return send_file(path, mimetype='image/png')


@socketio.on('save_drawing')
def handle_save_drawing(data):
    emit('save_image', data, broadcast=True)


@socketio.on("show_podium")
def io_show_podium():
    emit("show_podium", Globals.game_data['ratings'], broadcast=True)

    users = []
    for username, ratings in Globals.game_data["ratings"].items():
        total_points = ratings['fav'] + 2 * ratings['admin']
        users.append((username, total_points))
    top_users = sorted(users, key=lambda x: x[1], reverse=True)[:3]

    emit("podium_info", top_users)


@socketio.on("set_already_begun")
def io_set_already_begun(state: bool):
    Globals.actually_started = state


@socketio.on("admin_rating")
def io_admin_rating(data):
    username = data['username']
    rating = data['rating']

    if Globals.game_data["ratings"].get(username) is None:
        print("\033[1;31m;[F] uh oh. rating for unknown user (admin)\033[0m")
        return

    Globals.game_data['ratings'][username]['fav'] += rating
    print(f"\033[1;32m[MONITOR] Got admin rating for {username}\033[0m")
    emit("monitor_remove_rating", username)


if __name__ == "__main__":
    socketio.run(app, allow_unsafe_werkzeug=True, debug=True)
