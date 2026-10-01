from datetime import datetime, timedelta
from app import create_app
from config import TestConfig
from models import db, User, Door, RateLimitBlock
from routes.web import rate_limit_error


def test_sixth_attempt_blocked_and_stored(make_user, main_door, request_door):
    user = make_user()
    assert [request_door(user, main_door).status_code for _ in range(5)] == [200] * 5
    assert request_door(user, main_door).status_code == 429
    block = RateLimitBlock.query.one()
    assert (block.user_id, block.door_id) == (user.id, main_door.id)
    assert timedelta(seconds=290) < block.blocked_until - datetime.utcnow() <= timedelta(seconds=300)


def test_block_expires(make_user, main_door, request_door):
    user = make_user()
    for _ in range(6):
        request_door(user, main_door)
    RateLimitBlock.query.update({RateLimitBlock.blocked_until: datetime.utcnow() - timedelta(seconds=1)})
    db.session.execute(db.text("UPDATE access_logs SET timestamp = :t"), {"t": datetime.utcnow() - timedelta(minutes=2)})
    db.session.commit()
    assert request_door(user, main_door).status_code == 200


def test_limits_come_from_config(app, make_user, main_door, request_door):
    app.config["RATE_LIMIT_ATTEMPTS"] = 2
    user = make_user()
    assert [request_door(user, main_door).status_code for _ in range(3)] == [200, 200, 429]


def test_block_survives_restart(tmp_path):
    class FileConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'gatekeeper.db'}"

    first = create_app(FileConfig)
    with first.app_context():
        user = User(first_name="R", last_name="S", username="r.s", email="r@test.local", role="resident")
        user.set_password("Passw0rd!")
        door = Door(name="Main", door_type="main")
        db.session.add_all([user, door])
        db.session.flush()
        db.session.add(RateLimitBlock(user_id=user.id, door_id=door.id, blocked_until=datetime.utcnow() + timedelta(minutes=5)))
        db.session.commit()
        ids = (user.id, door.id)
        db.engine.dispose()

    restarted = create_app(FileConfig)
    with restarted.app_context():
        assert rate_limit_error(*ids) is not None
        db.engine.dispose()
