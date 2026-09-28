from models import db, User

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