"""
Broadcast Manager Module
Handles concurrent message broadcasting across multiple accounts and groups.
Manages broadcast sessions, timing, and error handling.
"""

import asyncio
from datetime import datetime
from app.models import (
    add_broadcast_history, get_groups_by_account, get_all_accounts, add_log
)
from app.telegram_manager import get_or_create_client

# Active broadcast sessions
active_broadcasts = {}

class BroadcastSession:
    """
    Represents an active broadcast session.
    
    Attributes:
        session_id (str): Unique broadcast session ID
        message (str): Message to broadcast
        delay (float): Delay between sends in seconds
        auto_repeat (bool): Whether to repeat broadcasts
        repeat_interval (int): Interval for auto-repeat in minutes
        is_running (bool): Current run status
    """
    
    def __init__(self, session_id, message, delay=1.0, auto_repeat=False, repeat_interval=60):
        """
        Initialize broadcast session.
        
        Args:
            session_id (str): Unique session ID
            message (str): Message text
            delay (float): Delay between sends
            auto_repeat (bool): Enable auto-repeat
            repeat_interval (int): Repeat interval in minutes
        """
        self.session_id = session_id
        self.message = message
        self.delay = max(Config.MIN_BROADCAST_DELAY, min(delay, Config.MAX_BROADCAST_DELAY))
        self.auto_repeat = auto_repeat
        self.repeat_interval = repeat_interval
        self.is_running = False
        self.stats = {
            'sent': 0,
            'failed': 0,
            'total': 0,
            'start_time': None,
            'end_time': None
        }

class BroadcastManager:
    """
    Manages broadcast operations across multiple accounts.
    
    Handles concurrent sending, error management, and session tracking.
    """
    
    @staticmethod
    async def start_broadcast(session_id, message, delay=1.0, auto_repeat=False, 
                             repeat_interval=60, account_ids=None):
        """
        Start a new broadcast session.
        
        Args:
            session_id (str): Unique session ID
            message (str): Message to broadcast
            delay (float): Delay between sends
            auto_repeat (bool): Enable auto-repeat
            repeat_interval (int): Repeat interval in minutes
            account_ids (list, optional): Specific accounts to broadcast from
            
        Returns:
            dict: Session status and details
        """
        try:
            from app.config import Config
            
            # Create session
            session = BroadcastSession(session_id, message, delay, auto_repeat, repeat_interval)
            session.is_running = True
            session.stats['start_time'] = datetime.now().isoformat()
            active_broadcasts[session_id] = session
            
            add_log(None, None, f'Broadcast session {session_id} started')
            
            # Get accounts to use
            if account_ids:
                accounts = [{'id': aid} for aid in account_ids]
            else:
                accounts = get_all_accounts()
            
            # Start broadcast coroutine
            asyncio.create_task(BroadcastManager._broadcast_loop(
                session, accounts, message, delay
            ))
            
            return {'success': True, 'session_id': session_id}
            
        except Exception as e:
            add_log(None, None, f'Broadcast start error: {str(e)}', 'ERROR')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def _broadcast_loop(session, accounts, message, delay):
        """
        Main broadcast loop for sending messages.
        
        Args:
            session (BroadcastSession): Current session
            accounts (list): Accounts to broadcast from
            message (str): Message to send
            delay (float): Delay between sends
        """
        try:
            from app.config import Config
            
            while session.is_running:
                # Create tasks for all accounts
                tasks = []
                
                for account in accounts:
                    account_id = account['id']
                    # Get selected groups for this account
                    groups = get_groups_by_account(account_id, only_selected=True)
                    
                    for group in groups:
                        task = BroadcastManager._send_to_group(
                            session, account_id, group['group_id'], message, delay
                        )
                        tasks.append(task)
                
                # Execute all sends concurrently
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Update session stats
                session.stats['end_time'] = datetime.now().isoformat()
                
                # Check if should repeat
                if not session.auto_repeat:
                    session.is_running = False
                    break
                
                # Wait for repeat interval
                await asyncio.sleep(session.repeat_interval * 60)
                
        except Exception as e:
            add_log(None, None, f'Broadcast loop error: {str(e)}', 'ERROR')
            session.is_running = False
    
    @staticmethod
    async def _send_to_group(session, account_id, group_id, message, delay):
        """
        Send message to a single group.
        
        Args:
            session (BroadcastSession): Broadcast session
            account_id (int): Account ID
            group_id (int): Group ID
            message (str): Message text
            delay (float): Delay before sending
        """
        try:
            # Wait for delay
            await asyncio.sleep(delay)
            
            # Get or create client
            client = get_or_create_client(account_id)
            if not client:
                add_log(account_id, account_id, 'Client not found', 'ERROR')
                return
            
            # Send message
            result = await client.send_message(group_id, message)
            
            if result['success']:
                session.stats['sent'] += 1
                add_broadcast_history(account_id, group_id, message, 'sent')
                add_log(account_id, account_id, f'Message sent to group {group_id}')
            else:
                session.stats['failed'] += 1
                add_broadcast_history(account_id, group_id, message, 'failed', result.get('error'))
                add_log(account_id, account_id, f'Failed to send to group {group_id}: {result.get("error")}', 'ERROR')
            
            session.stats['total'] += 1
            
        except Exception as e:
            session.stats['failed'] += 1
            session.stats['total'] += 1
            add_log(account_id, account_id, f'Send error: {str(e)}', 'ERROR')
    
    @staticmethod
    def stop_broadcast(session_id):
        """
        Stop an active broadcast session.
        
        Args:
            session_id (str): Session ID to stop
            
        Returns:
            dict: Final session statistics
        """
        if session_id not in active_broadcasts:
            return {'success': False, 'error': 'Session not found'}
        
        session = active_broadcasts[session_id]
        session.is_running = False
        session.stats['end_time'] = datetime.now().isoformat()
        
        add_log(None, None, f'Broadcast session {session_id} stopped')
        
        return {
            'success': True,
            'session_id': session_id,
            'stats': session.stats
        }
    
    @staticmethod
    def get_broadcast_status(session_id):
        """
        Get current status of a broadcast session.
        
        Args:
            session_id (str): Session ID
            
        Returns:
            dict: Session status and statistics
        """
        if session_id not in active_broadcasts:
            return None
        
        session = active_broadcasts[session_id]
        return {
            'session_id': session_id,
            'is_running': session.is_running,
            'stats': session.stats,
            'message': session.message[:100] + '...' if len(session.message) > 100 else session.message
        }
    
    @staticmethod
    def get_all_broadcasts():
        """
        Get all active broadcast sessions.
        
        Returns:
            dict: Dictionary of all active sessions
        """
        return {
            session_id: BroadcastManager.get_broadcast_status(session_id)
            for session_id in active_broadcasts.keys()
        }

# Import Config at the end to avoid circular imports
try:
    from app.config import Config
except ImportError:
    pass
