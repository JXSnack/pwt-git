import time


class Globals:
    key = "dev"
    user_data = {}
    game_data = {}
    started = False
    actually_started = False
    timer_max = 3
    timer_warn = 5


def millis():
    return round(time.time() * 1000)


def check_dict_case_insensitive(d: dict, key: str) -> bool:
    key_lower = key.lower()
    return any(k.lower() == key_lower for k in d)
