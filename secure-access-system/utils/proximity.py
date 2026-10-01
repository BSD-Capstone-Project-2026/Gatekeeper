import ipaddress
from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer


def on_building_network(address):
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in ipaddress.ip_network(network) for network in current_app.config["BUILDING_NETWORKS"])


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="door-proximity")


def issue_proximity_token(door_id):
    return _serializer().dumps({"door": door_id})


def proximity_verified(token, door_id):
    if not token:
        return False
    try:
        return _serializer().loads(token, max_age=current_app.config["PROXIMITY_TOKEN_SECONDS"]).get("door") == door_id
    except (BadSignature, AttributeError):
        return False
