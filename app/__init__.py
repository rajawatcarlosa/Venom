"""
Telegram Multi Account Broadcaster Application
Main Flask application package initialization
"""

from flask import Flask
from app.config import Config

# Flask app instance
app = None

def create_app():
    """
    Application factory function.
    Creates and configures the Flask application.
    
    Returns:
        Flask: Configured Flask application instance
    """
    global app
    
    app = Flask(__name__, 
               template_folder='templates',
               static_folder='static')
    
    # Load configuration
    app.config.from_object(Config)
    
    # Initialize database
    from app.models import init_db
    init_db()
    
    # Register blueprints
    from app.routes import main_bp, accounts_bp, groups_bp, broadcast_bp, logs_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(broadcast_bp)
    app.register_blueprint(logs_bp)
    
    return app
