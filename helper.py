import time


class Globals:
    key = "dev"
    user_data = {}
    game_data = {}
    started = False
    timer_max = 30
    timer_warn = 5


def millis():
    return round(time.time() * 1000)
