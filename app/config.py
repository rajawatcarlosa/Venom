"""
Application Configuration
Centralized configuration management for the Flask application
Supports persistent API credentials storage
"""

import os
import json
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent
APP_DIR = Path(__file__).parent

class Config:
    """
    Base configuration class with essential Flask settings.
    Supports persistent credential storage for one-time setup.
    """
    
    # Flask settings
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    FLASK_DEBUG = os.environ.get('FLASK_DEBUG', False)
    SECRET_KEY = os.environ.get('SECRET_KEY', 'telegram-broadcaster-prod-key-2024')
    JSON_SORT_KEYS = False
    
    # Server settings
    FLASK_HOST = '0.0.0.0'
    FLASK_PORT = 5000
    THREADED = True
    
    # Database settings
    DATABASE_PATH = str(APP_DIR / 'database' / 'broadcaster.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Telegram settings
    TELEGRAM_API_ID_DEFAULT = None
    TELEGRAM_API_HASH_DEFAULT = None
    TELEGRAM_DEFAULT_DELAY = 1  # Seconds between sends
    TELEGRAM_FLOOD_WAIT_HANDLE = True
    TELEGRAM_CONNECTION_TIMEOUT = 30  # Seconds
    TELEGRAM_REQUEST_TIMEOUT = 15  # Seconds
    
    # Paths
    SESSION_PATH = str(APP_DIR / 'sessions')
    LOG_PATH = str(APP_DIR / 'logs')
    UPLOAD_PATH = str(APP_DIR / 'static' / 'uploads')
    CREDENTIALS_PATH = str(APP_DIR / 'config' / 'credentials.json')
    
    # Broadcast settings
    MAX_MESSAGE_LENGTH = 4096
    MIN_BROADCAST_DELAY = 0.5  # Minimum seconds between sends
    MAX_BROADCAST_DELAY = 60  # Maximum seconds between sends
    MAX_CONCURRENT_ACCOUNTS = 10
    
    # Logging settings
    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
    
    # File upload settings
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max upload
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
    
    @staticmethod
    def init_directories():
        """Initialize required directories."""
        directories = [
            Config.SESSION_PATH,
            Config.LOG_PATH,
            Config.UPLOAD_PATH,
            str(APP_DIR / 'database'),
            str(APP_DIR / 'config')
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def save_credentials(api_id, api_hash):
        """Save API credentials to persistent file."""
        Config.init_directories()
        creds = {'api_id': api_id, 'api_hash': api_hash}
        with open(Config.CREDENTIALS_PATH, 'w') as f:
            json.dump(creds, f)
    
    @staticmethod
    def load_credentials():
        """Load saved API credentials."""
        if Path(Config.CREDENTIALS_PATH).exists():
            try:
                with open(Config.CREDENTIALS_PATH, 'r') as f:
                    return json.load(f)
            except:
                return None
        return None
    
    @staticmethod
    def delete_credentials():
        """Delete saved credentials."""
        cred_file = Path(Config.CREDENTIALS_PATH)
        if cred_file.exists():
            cred_file.unlink()


# Initialize directories on import
Config.init_directories()
