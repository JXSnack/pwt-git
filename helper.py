import time


class Globals:
    key = "dev"
    user_data = {}
    game_data = {}
    started = False


def millis():
    return round(time.time() * 1000)
