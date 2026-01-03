from enum import IntEnum, StrEnum


class PandoraEngineCommand(IntEnum):
    RUN_ENGINE = 4
    STOP_ENGINE = 8


class PandoraCommand(IntEnum):
    START = PandoraEngineCommand.RUN_ENGINE
    STOP = PandoraEngineCommand.STOP_ENGINE


class AuthResponseField(StrEnum):
    STATUS = "status"
    SESSION_ID = "session_id"
    USER_ID = "user_id"


class PandoraEndpoints:
    host = "p-on.ru"
    base_url = "https://" + host
    login = "/api/users/login"
    devices = "/api/devices"
    update = "/api/updates"
    command = "/api/devices/command"
    profile = "/api/users/profile"
    alive = "/api/iamalive"  # {"status":"you are alive"}
