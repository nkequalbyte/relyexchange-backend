from flask import Flask
from app.config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register Blueprints
    from app.endpoints.contacts import contacts_bp
    from app.endpoints.users import users_bp
    app.register_blueprint(contacts_bp, url_prefix='/contacts')
    app.register_blueprint(users_bp, url_prefix='/users')

    return app
