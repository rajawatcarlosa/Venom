# Telegram Multi Account Broadcaster

A modern, user-friendly Flask desktop application for managing multiple Telegram accounts and broadcasting messages to groups and channels simultaneously.

## Features

### 🔐 Multi-Account Management
- Add and manage unlimited Telegram accounts
- Secure API credentials storage
- Automatic session persistence
- One-click account reconnection
- Real-time account status monitoring

### 📱 Group Management
- Load groups and channels from each Telegram account
- Multi-select group management
- Save group preferences per account
- Prevent duplicate sends
- Quick refresh functionality

### 📢 Broadcasting System
- Send messages to multiple groups simultaneously
- Configurable send delays
- Auto-repeat messaging
- Concurrent multi-account sending
- FloodWait error handling
- Stop/pause functionality

### 📊 Dashboard & Analytics
- Real-time statistics
- Account overview
- Message sent counter
- Recent activity feed
- Performance metrics

### 📝 Logging & Monitoring
- Comprehensive action logging
- Real-time log viewer
- Persistent log storage
- Detailed error tracking
- Timestamped events

### 🎨 Modern UI
- Bootstrap 5 dark theme
- Responsive design
- Mobile-friendly interface
- Smooth animations
- Intuitive navigation

## System Requirements

- **OS**: Windows 7 or later
- **Python**: 3.12 or higher
- **RAM**: Minimum 2GB (4GB recommended)
- **Internet**: Required for Telegram connectivity
- **Telegram Account**: At least one Telegram account

## Installation

### Quick Start (Recommended)

1. **Extract the project** to your desired location
2. **Double-click** `start.bat`
3. Wait for the application to start automatically
4. Your browser will open to `http://localhost:5000`

### Manual Installation

1. **Install Python 3.12+**
   - Download from [python.org](https://www.python.org/)
   - Ensure "Add Python to PATH" is checked during installation

2. **Clone or extract the repository**
   ```bash
   cd path/to/Telegram-Broadcaster
   ```

3. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Initialize database**
   ```bash
   python -c "from app.models import init_db; init_db()"
   ```

6. **Start the application**
   ```bash
   python app.py
   ```

## First-Time Setup

### Adding a Telegram Account

1. Go to the **Accounts** page
2. Click **Add New Account**
3. Enter your **Telegram API ID** and **API HASH**
   - Get these from [my.telegram.org](https://my.telegram.org/auth)
4. Enter your **Telegram phone number**
5. Complete the **verification code** from Telegram
6. Your account is now connected!

### Loading Groups

1. Go to **Group Management**
2. Select an account from the dropdown
3. Click **Load Groups** to fetch all groups/channels
4. Check the groups you want to target
5. Click **Save Selection**

### Starting a Broadcast

1. Navigate to **Broadcast**
2. Enter your message
3. Set the delay between sends (in seconds)
4. (Optional) Enable auto-repeat and set interval
5. Click **Start Broadcast**
6. Monitor progress in real-time
7. Click **Stop** to end the broadcast

## Configuration

### API Credentials

You need Telegram API credentials to use this application:

1. Visit [my.telegram.org](https://my.telegram.org/auth)
2. Login with your Telegram account
3. Go to "API Development Tools"
4. Create a new application
5. Copy your **API ID** and **API HASH**

### Application Settings

Edit `app/config.py` to customize:

```python
# Flask settings
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000
FLASK_DEBUG = False

# Telegram settings
TELEGRAM_DEFAULT_DELAY = 1  # seconds between sends
TELEGRAM_FLOOD_WAIT_HANDLE = True

# Database
DATABASE_PATH = 'app/database/broadcaster.db'

# Session management
SESSION_PATH = 'app/sessions'
LOG_PATH = 'app/logs'
```

## Database Structure

### Tables

- **accounts**: Stored Telegram accounts with phone numbers and status
- **groups**: Groups/channels associated with accounts
- **broadcast_settings**: User preferences for broadcasts
- **broadcast_history**: Records of all sent broadcasts
- **logs**: Application events and errors

## Usage Examples

### Broadcasting to Single Group

1. Add one Telegram account
2. Load and select one group
3. Enter message
4. Click Start Broadcast

### Broadcasting to Multiple Groups Across Multiple Accounts

1. Add 2+ Telegram accounts
2. For each account, load and select desired groups
3. Enter message
4. Enable auto-repeat if needed
5. Click Start Broadcast
- Application will send concurrently from all accounts

## Troubleshooting

### Issue: "API ID/HASH not found"
**Solution**: Register at [my.telegram.org](https://my.telegram.org/auth)

### Issue: "Phone number is invalid"
**Solution**: Use the full international format (e.g., +1234567890)

### Issue: "Verification code expired"
**Solution**: Request a new code and enter quickly (valid for ~10 minutes)

### Issue: "FloodWait" error
**Solution**: Application automatically handles this. Wait for the indicated duration.

### Issue: "Connection failed"
**Solution**: 
- Check internet connection
- Verify Telegram is not blocked
- Restart the application
- Check firewall settings

### Issue: "Database locked"
**Solution**: Close all instances of the application and restart

### Issue: Application won't start
**Solution**:
1. Ensure Python 3.12+ is installed
2. Run in command prompt to see error messages
3. Delete `venv` folder and run `start.bat` again

## Security Notes

⚠️ **Important Security Information**

- **Never share** your API ID/HASH with anyone
- **Never share** your phone numbers or session files
- **Keep credentials private** - store in secure locations
- **Backup important data** before major updates
- **Use strong Telegram passwords** - this protects your account
- **Session files** in `app/sessions/` contain authentication data - treat as sensitive
- **Always verify group messages** before broadcasting
- **Monitor logs** for suspicious activity

## File Structure

```
Telegram-Broadcaster/
├── app/
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── accounts.html
│   │   ├── groups.html
│   │   ├── broadcast.html
│   │   ├── logs.html
│   │   └── dashboard.html
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── js/
│   │   │   ├── main.js
│   │   │   └── broadcast.js
│   │   └── uploads/
│   ├── database/
│   ├── sessions/
│   ├── logs/
│   ├── __init__.py
│   ├── app.py
│   ├── models.py
│   ├── telegram_manager.py
│   ├── broadcast_manager.py
│   └── config.py
├── requirements.txt
├── start.bat
└── README.md
```

## Performance Tips

1. **Optimal Delay**: Use 1-2 seconds between sends to avoid FloodWait
2. **Account Load**: 5+ concurrent accounts works smoothly
3. **Message Size**: Keep messages under 4096 characters
4. **Group Count**: Can handle 100+ groups efficiently
5. **Auto-repeat**: Minimum 5-minute intervals recommended

## Advanced Features

### Custom Delays
- Set different delays for different account types
- Configure in Group Management page

### Selective Broadcasting
- Choose specific groups before each broadcast
- Broadcast to specific accounts only

### Message Templates
- Save common messages
- Use placeholders for dynamic content

### Scheduled Broadcasts
- Set broadcasts to run at specific times
- Available in dashboard

## API Reference

For advanced customization, key modules are:

- `telegram_manager.py`: Telegram API interactions
- `broadcast_manager.py`: Broadcasting logic
- `models.py`: Database models

## Contributing

Contributions are welcome! Areas for enhancement:

- Media file broadcasting (images, videos)
- Message scheduling
- Advanced filtering
- Statistics export
- Multi-language support

## License

This project is provided as-is for personal and commercial use.

## Support

For issues or questions:

1. Check the Troubleshooting section
2. Review logs in the Logs page
3. Check application console for error messages

## Disclaimer

- This tool is for legitimate communication purposes
- Respect Telegram's Terms of Service
- Use responsibly and ethically
- Do not use for spam or harassment
- Telegram may limit or block accounts that abuse the service
- User is responsible for compliance with all applicable laws

---

**Version**: 1.0.0  
**Last Updated**: 2026-06-07  
**Python**: 3.12+  
**Platform**: Windows 7+
