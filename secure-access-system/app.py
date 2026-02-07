# app.py
# Main application entry point
from flask import Flask, render_template
from flask import Flask
from flask_jwt_extended import JWTManager
from config import Config
from models import db, User
from routes.auth import auth_bp
from routes.users import users_bp
from routes.protected import protected_bp
from routes.web import web_bp 
from routes.dashboard import dashboard_bp


from flask_login import LoginManager

def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(Config)
    app.register_blueprint(dashboard_bp)

    


    # Initialize extensions
    db.init_app(app)
    JWTManager(app)

    # --- Flask-Login setup ---
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "web.login"  # redirect to login page if not authenticated

    @login_manager.user_loader
    def load_user(user_id):
        
        return User.query.get(int(user_id))
    # ------------------------

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(protected_bp)
    app.register_blueprint(web_bp)

    # Create tables + seed demo management user
    with app.app_context():
       # if app.config.get('RESET_DB'):
        #    print("🔄 Resetting database...")
         #   db.drop_all()
        
        db.create_all()

        # Demo user
        demo_user = User.query.filter_by(email=Config.DEMO_USER_EMAIL).first()
        if not demo_user:
            demo_user = User(
                first_name="Building",
                last_name="Management",
                username="building.management",
                email=Config.DEMO_USER_EMAIL,
                role="management"
            )
            demo_user.set_password(Config.DEMO_USER_PASSWORD)
            db.session.add(demo_user)
            print("✅ Demo management account created")

        # Backup admin
        backup_admin = User.query.filter_by(email="admin@backup.local").first()
        if not backup_admin:
            backup_admin = User(
                first_name="Backup",
                last_name="Admin",
                username="backup.admin",
                email="admin@backup.local",
                role="management"
            )
            backup_admin.set_password("BackupPass123")
            db.session.add(backup_admin)
            print("✅ Backup admin account created")

        db.session.commit()

    @app.route("/")
    def home():
        return "Secure Access System – Phase 1 Step 1 Running"

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)