import pytest
from app import create_app
from models import db, User

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'   # in-memory for tests
    with app.app_context():
        db.create_all()
        yield app
    db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_transaction_rollback(app):
    with app.app_context():
        # Create a user but don't commit yet
        user = User(
            first_name="Test",
            last_name="User",
            username="test.user",
            email="test@test.com",
            role="resident"
        )
        db.session.add(user)
        # Simulate a crash before commit
        try:
            raise Exception("Simulated crash")
            db.session.commit()
        except:
            db.session.rollback()
        # Verify user not saved
        assert User.query.filter_by(email="test@test.com").first() is None