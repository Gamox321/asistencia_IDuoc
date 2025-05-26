from flask import Flask
from .routes import main
import os

def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)  # Para sesiones

    app.register_blueprint(main)

    return app
