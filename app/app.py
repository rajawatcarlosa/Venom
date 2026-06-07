"""
Main Flask Application Entry Point
Initializes and runs the Telegram Multi Account Broadcaster application.
"""

import os
import sys
import webbrowser
from pathlib import Path
from app import create_app
from app.config import Config
from app.models import init_db, add_log

def run_app():
    """
    Initialize and run the Flask application.
    """
    # Ensure directories exist
    Config.init_directories()
    
    # Initialize database
    print('Initializing database...')
    init_db()
    
    # Create Flask app
    print('Creating Flask application...')
    app = create_app()
    
    # Add startup message
    print('\n' + '='*60)
    print('Telegram Multi Account Broadcaster')
    print('='*60)
    print(f'Server: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}')
    print('Opening browser in 2 seconds...')
    print('Press Ctrl+C to stop')
    print('='*60 + '\n')
    
    # Open browser
    def open_browser():
        import time
        time.sleep(2)
        webbrowser.open(f'http://localhost:{Config.FLASK_PORT}')
    
    import threading
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # Log startup
    add_log('app_start', None, 'Application started')
    
    # Run app
    try:
        app.run(
            host=Config.FLASK_HOST,
            port=Config.FLASK_PORT,
            debug=Config.FLASK_DEBUG,
            threaded=Config.THREADED,
            use_reloader=False  # Disable reloader for Windows compatibility
        )
    except KeyboardInterrupt:
        print('\n\nShutting down...')
        add_log('app_stop', None, 'Application stopped')
    except Exception as e:
        print(f'Error running application: {e}')
        add_log('app_error', None, f'Application error: {str(e)}', 'ERROR')
        sys.exit(1)

if __name__ == '__main__':
    run_app()
