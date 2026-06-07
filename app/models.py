"""
Database Models
Defines SQLAlchemy models for the application database.
Handles accounts, groups, broadcasts, and logging.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from app.config import Config

# Database path
DB_PATH = Config.DATABASE_PATH

def get_db():
    """
    Get database connection.
    
    Returns:
        sqlite3.Connection: Database connection object
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initialize database with required tables.
    Creates all necessary tables if they don't exist.
    """
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Accounts table - stores Telegram accounts
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone_number TEXT UNIQUE NOT NULL,
        api_id INTEGER NOT NULL,
        api_hash TEXT NOT NULL,
        status TEXT DEFAULT 'disconnected',
        user_id INTEGER,
        first_name TEXT,
        last_name TEXT,
        username TEXT,
        is_bot INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_connected TIMESTAMP,
        last_error TEXT
    )
    ''')
    
    # Groups table - stores groups/channels from accounts
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        group_name TEXT NOT NULL,
        group_type TEXT,
        is_channel INTEGER DEFAULT 0,
        members_count INTEGER,
        is_selected INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(account_id) REFERENCES accounts(id),
        UNIQUE(account_id, group_id)
    )
    ''')
    
    # Broadcast settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS broadcast_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER,
        delay_seconds REAL DEFAULT 1.0,
        auto_repeat INTEGER DEFAULT 0,
        repeat_interval_minutes INTEGER DEFAULT 60,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        FOREIGN KEY(account_id) REFERENCES accounts(id)
    )
    ''')
    
    # Broadcast history table - logs all broadcasts
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS broadcast_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        error_message TEXT,
        sent_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(account_id) REFERENCES accounts(id),
        FOREIGN KEY(group_id) REFERENCES groups(id)
    )
    ''')
    
    # Logs table - application event logging
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        account_id INTEGER,
        message TEXT,
        level TEXT DEFAULT 'INFO',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(account_id) REFERENCES accounts(id)
    )
    ''')
    
    # Create indices for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_accounts_phone ON accounts(phone_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_groups_account ON groups(account_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_broadcast_account ON broadcast_history(account_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_created ON logs(created_at)')
    
    conn.commit()
    conn.close()

# ==================== Account Operations ====================

def add_account(phone_number, api_id, api_hash, user_id=None, first_name=None, 
                last_name=None, username=None, is_bot=False):
    """
    Add a new Telegram account to the database.
    
    Args:
        phone_number (str): Telegram phone number
        api_id (int): Telegram API ID
        api_hash (str): Telegram API hash
        user_id (int, optional): Telegram user ID
        first_name (str, optional): User's first name
        last_name (str, optional): User's last name
        username (str, optional): Telegram username
        is_bot (bool, optional): Whether account is a bot
        
    Returns:
        int: ID of the added account or None on error
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO accounts 
        (phone_number, api_id, api_hash, user_id, first_name, last_name, username, is_bot, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'authorized')
        ''', (phone_number, api_id, api_hash, user_id, first_name, last_name, username, int(is_bot)))
        
        conn.commit()
        account_id = cursor.lastrowid
        conn.close()
        
        add_log('account_added', account_id, f'Account {phone_number} added successfully')
        return account_id
    except Exception as e:
        add_log(None, None, f'Error adding account: {str(e)}', 'ERROR')
        return None

def get_all_accounts():
    """
    Get all accounts from database.
    
    Returns:
        list: List of all accounts with their details
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM accounts ORDER BY created_at DESC')
    accounts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return accounts

def get_account(account_id):
    """
    Get specific account by ID.
    
    Args:
        account_id (int): Account ID
        
    Returns:
        dict: Account details or None if not found
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM accounts WHERE id = ?', (account_id,))
    account = cursor.fetchone()
    conn.close()
    return dict(account) if account else None

def get_account_by_phone(phone_number):
    """
    Get account by phone number.
    
    Args:
        phone_number (str): Telegram phone number
        
    Returns:
        dict: Account details or None if not found
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM accounts WHERE phone_number = ?', (phone_number,))
    account = cursor.fetchone()
    conn.close()
    return dict(account) if account else None

def update_account_status(account_id, status, error_message=None):
    """
    Update account connection status.
    
    Args:
        account_id (int): Account ID
        status (str): New status (authorized, unauthorized, error, etc.)
        error_message (str, optional): Error message if status is error
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE accounts 
    SET status = ?, last_connected = CURRENT_TIMESTAMP, last_error = ?
    WHERE id = ?
    ''', (status, error_message, account_id))
    
    conn.commit()
    conn.close()

def delete_account(account_id):
    """
    Delete an account and its associated data.
    
    Args:
        account_id (int): Account ID to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Delete associated data
        cursor.execute('DELETE FROM groups WHERE account_id = ?', (account_id,))
        cursor.execute('DELETE FROM broadcast_history WHERE account_id = ?', (account_id,))
        cursor.execute('DELETE FROM broadcast_settings WHERE account_id = ?', (account_id,))
        cursor.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
        
        conn.commit()
        conn.close()
        
        add_log('account_deleted', account_id, f'Account {account_id} deleted')
        return True
    except Exception as e:
        add_log(None, None, f'Error deleting account: {str(e)}', 'ERROR')
        return False

# ==================== Group Operations ====================

def add_group(account_id, group_id, group_name, group_type='group', 
              is_channel=False, members_count=0, is_selected=False):
    """
    Add a group/channel to the database.
    
    Args:
        account_id (int): Account ID that owns the group
        group_id (int): Telegram group ID
        group_name (str): Group name
        group_type (str): Type of group (group, supergroup, channel)
        is_channel (bool): Whether it's a channel
        members_count (int): Number of members
        is_selected (bool): Whether it's selected for broadcasting
        
    Returns:
        int: ID of the added group or None on error
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO groups 
        (account_id, group_id, group_name, group_type, is_channel, members_count, is_selected)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (account_id, group_id, group_name, group_type, int(is_channel), members_count, int(is_selected)))
        
        conn.commit()
        group_db_id = cursor.lastrowid
        conn.close()
        
        return group_db_id
    except Exception as e:
        add_log(account_id, None, f'Error adding group: {str(e)}', 'ERROR')
        return None

def get_groups_by_account(account_id, only_selected=False):
    """
    Get groups for a specific account.
    
    Args:
        account_id (int): Account ID
        only_selected (bool): Only get selected groups
        
    Returns:
        list: List of groups
    """
    conn = get_db()
    cursor = conn.cursor()
    
    if only_selected:
        cursor.execute(
            'SELECT * FROM groups WHERE account_id = ? AND is_selected = 1 ORDER BY group_name',
            (account_id,)
        )
    else:
        cursor.execute(
            'SELECT * FROM groups WHERE account_id = ? ORDER BY group_name',
            (account_id,)
        )
    
    groups = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return groups

def update_group_selection(account_id, group_id, is_selected):
    """
    Update whether a group is selected for broadcasting.
    
    Args:
        account_id (int): Account ID
        group_id (int): Telegram group ID
        is_selected (bool): Selection status
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE groups 
    SET is_selected = ?
    WHERE account_id = ? AND group_id = ?
    ''', (int(is_selected), account_id, group_id))
    
    conn.commit()
    conn.close()

def clear_groups_for_account(account_id):
    """
    Clear all groups for an account (used when reloading groups).
    
    Args:
        account_id (int): Account ID
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM groups WHERE account_id = ?', (account_id,))
    conn.commit()
    conn.close()

# ==================== Broadcast Operations ====================

def add_broadcast_history(account_id, group_id, message, status='sent', error_message=None):
    """
    Log a broadcast message to history.
    
    Args:
        account_id (int): Account ID
        group_id (int): Group ID
        message (str): Message text
        status (str): Broadcast status (sent, failed, skipped)
        error_message (str, optional): Error details if failed
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO broadcast_history 
        (account_id, group_id, message, status, error_message, sent_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (account_id, group_id, message, status, error_message))
        
        conn.commit()
        conn.close()
    except Exception as e:
        add_log(account_id, None, f'Error logging broadcast: {str(e)}', 'ERROR')

def get_broadcast_history(account_id=None, limit=50):
    """
    Get broadcast history.
    
    Args:
        account_id (int, optional): Filter by account
        limit (int): Maximum number of records to return
        
    Returns:
        list: Broadcast history records
    """
    conn = get_db()
    cursor = conn.cursor()
    
    if account_id:
        cursor.execute('''
        SELECT * FROM broadcast_history 
        WHERE account_id = ? 
        ORDER BY sent_at DESC 
        LIMIT ?
        ''', (account_id, limit))
    else:
        cursor.execute('''
        SELECT * FROM broadcast_history 
        ORDER BY sent_at DESC 
        LIMIT ?
        ''', (limit,))
    
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history

def get_broadcast_stats():
    """
    Get broadcast statistics.
    
    Returns:
        dict: Statistics including total sent, failed, etc.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        COUNT(*) as total_broadcasts,
        SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as total_sent,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as total_failed
    FROM broadcast_history
    ''')
    
    stats = dict(cursor.fetchone())
    conn.close()
    return stats

# ==================== Logging Operations ====================

def add_log(event_type, account_id, message, level='INFO'):
    """
    Add an event to the application logs.
    
    Args:
        event_type (str): Type of event (login, broadcast, error, etc.)
        account_id (int, optional): Associated account ID
        message (str): Log message
        level (str): Log level (INFO, WARNING, ERROR, DEBUG)
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO logs (event_type, account_id, message, level)
        VALUES (?, ?, ?, ?)
        ''', (event_type, account_id, message, level))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'Error writing to logs: {str(e)}')

def get_logs(limit=100):
    """
    Get application logs.
    
    Args:
        limit (int): Maximum number of log entries to return
        
    Returns:
        list: Log entries
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM logs 
    ORDER BY created_at DESC 
    LIMIT ?
    ''', (limit,))
    
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return logs

def get_logs_by_account(account_id, limit=50):
    """
    Get logs for a specific account.
    
    Args:
        account_id (int): Account ID
        limit (int): Maximum number of entries
        
    Returns:
        list: Log entries
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM logs 
    WHERE account_id = ? 
    ORDER BY created_at DESC 
    LIMIT ?
    ''', (account_id, limit))
    
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return logs

def clear_old_logs(days=30):
    """
    Clear logs older than specified days.
    
    Args:
        days (int): Clear logs older than this many days
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    DELETE FROM logs 
    WHERE created_at < datetime('now', '-' || ? || ' days')
    ''', (days,))
    conn.commit()
    conn.close()
