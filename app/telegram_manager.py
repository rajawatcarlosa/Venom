"""
Telegram Manager Module
Handles all Telegram API interactions using Telethon library.
Manages account connections, group loading, and message sending.
"""

import asyncio
import os
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    FloodWaitError,
    UnauthorizedError,
    PhoneNumberInvalidError
)
from telethon.tl.types import Chat, Channel, User
from app.config import Config
from app.models import (
    add_account, update_account_status, get_account, get_account_by_phone,
    add_group, clear_groups_for_account, add_log
)

# Dictionary to store active client instances
active_clients = {}

class TelegramManager:
    """
    Manages Telegram account connections and operations.
    
    Attributes:
        client (TelegramClient): Telethon client instance
        account_id (int): Associated account ID in database
        phone_number (str): Telegram phone number
    """
    
    def __init__(self, api_id, api_hash, phone_number, account_id=None):
        """
        Initialize Telegram Manager.
        
        Args:
            api_id (int): Telegram API ID
            api_hash (str): Telegram API hash
            phone_number (str): Telegram phone number
            account_id (int, optional): Database account ID
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.account_id = account_id
        
        # Create session file path
        session_file = os.path.join(Config.SESSION_PATH, f"{phone_number.replace('+', '')}.session")
        
        self.client = TelegramClient(
            session_file,
            self.api_id,
            self.api_hash,
            request_timeout=Config.TELEGRAM_REQUEST_TIMEOUT,
            connection_retries=3,
            retry_delay=2,
            request_retries=3
        )
    
    async def connect_and_login(self, verification_callback=None):
        """
        Connect to Telegram and perform login if needed.
        
        Args:
            verification_callback (callable, optional): Callback for 2FA code
            
        Returns:
            dict: Login result with status and user info
        """
        try:
            # Connect to Telegram
            await self.client.connect()
            add_log(self.account_id, self.account_id, f'Connected to Telegram for {self.phone_number}')
            
            # Check if already authorized
            if await self.client.is_user_authorized():
                user = await self.client.get_me()
                add_log(self.account_id, self.account_id, f'Account {self.phone_number} already authorized')
                return {
                    'success': True,
                    'authorized': True,
                    'user_id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name if user.last_name else '',
                    'username': user.username if user.username else '',
                    'is_bot': user.bot
                }
            
            # Start new login
            await self.client.start(
                phone=self.phone_number,
                code_callback=verification_callback,
                password=None  # Password handled separately
            )
            
            user = await self.client.get_me()
            add_log(self.account_id, self.account_id, f'Account {self.phone_number} logged in successfully')
            
            return {
                'success': True,
                'authorized': True,
                'user_id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name if user.last_name else '',
                'username': user.username if user.username else '',
                'is_bot': user.bot
            }
            
        except SessionPasswordNeededError:
            add_log(self.account_id, self.account_id, 'Two-factor authentication required')
            return {'success': False, 'error': '2FA', 'message': 'Two-factor authentication required'}
        except PhoneNumberInvalidError:
            add_log(self.account_id, self.account_id, 'Invalid phone number', 'ERROR')
            return {'success': False, 'error': 'invalid_phone', 'message': 'Invalid phone number'}
        except UnauthorizedError:
            add_log(self.account_id, self.account_id, 'Unauthorized access', 'ERROR')
            return {'success': False, 'error': 'unauthorized', 'message': 'Unauthorized access'}
        except FloodWaitError as e:
            add_log(self.account_id, self.account_id, f'FloodWait: {e.seconds} seconds', 'WARNING')
            return {'success': False, 'error': 'flood_wait', 'message': f'Too many requests. Wait {e.seconds}s'}
        except Exception as e:
            error_msg = str(e)
            add_log(self.account_id, self.account_id, f'Login error: {error_msg}', 'ERROR')
            return {'success': False, 'error': 'connection_error', 'message': error_msg}
    
    async def handle_2fa_password(self, password):
        """
        Handle two-factor authentication password.
        
        Args:
            password (str): 2FA password
            
        Returns:
            dict: Result of 2FA attempt
        """
        try:
            await self.client.sign_in(password=password)
            user = await self.client.get_me()
            add_log(self.account_id, self.account_id, '2FA authentication successful')
            
            return {
                'success': True,
                'user_id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name if user.last_name else '',
                'username': user.username if user.username else '',
                'is_bot': user.bot
            }
        except Exception as e:
            add_log(self.account_id, self.account_id, f'2FA error: {str(e)}', 'ERROR')
            return {'success': False, 'error': str(e)}
    
    async def disconnect(self):
        """
        Disconnect from Telegram.
        
        Returns:
            bool: True if successful
        """
        try:
            await self.client.disconnect()
            add_log(self.account_id, self.account_id, 'Disconnected from Telegram')
            return True
        except Exception as e:
            add_log(self.account_id, self.account_id, f'Disconnect error: {str(e)}', 'ERROR')
            return False
    
    async def get_groups(self):
        """
        Get all groups and channels for the account.
        
        Returns:
            list: List of groups/channels with details
        """
        try:
            groups = []
            async for dialog in self.client.iter_dialogs():
                entity = dialog.entity
                
                # Only get groups and channels
                if isinstance(entity, (Chat, Channel)):
                    group_info = {
                        'id': entity.id,
                        'name': entity.title,
                        'type': 'channel' if isinstance(entity, Channel) else 'group',
                        'is_channel': isinstance(entity, Channel),
                        'members': getattr(entity, 'participants_count', 0)
                    }
                    groups.append(group_info)
            
            add_log(self.account_id, self.account_id, f'Loaded {len(groups)} groups')
            return groups
            
        except FloodWaitError as e:
            add_log(self.account_id, self.account_id, f'FloodWait loading groups: {e.seconds}s', 'WARNING')
            return []
        except Exception as e:
            add_log(self.account_id, self.account_id, f'Error loading groups: {str(e)}', 'ERROR')
            return []
    
    async def send_message(self, group_id, message, retry_count=0, max_retries=3):
        """
        Send a message to a group/channel.
        
        Args:
            group_id (int): Telegram group ID
            message (str): Message text
            retry_count (int): Current retry count
            max_retries (int): Maximum retries
            
        Returns:
            dict: Send result with status and details
        """
        try:
            # Validate message
            if not message or len(message) > Config.MAX_MESSAGE_LENGTH:
                return {'success': False, 'error': 'invalid_message'}
            
            # Send message
            await self.client.send_message(group_id, message)
            add_log(self.account_id, self.account_id, f'Message sent to group {group_id}')
            
            return {'success': True, 'group_id': group_id}
            
        except FloodWaitError as e:
            if retry_count < max_retries:
                await asyncio.sleep(e.seconds)
                return await self.send_message(group_id, message, retry_count + 1, max_retries)
            else:
                add_log(self.account_id, self.account_id, 
                       f'FloodWait - max retries exceeded for group {group_id}', 'ERROR')
                return {'success': False, 'error': 'flood_wait', 'message': f'Wait {e.seconds} seconds'}
        
        except Exception as e:
            add_log(self.account_id, self.account_id, f'Error sending message: {str(e)}', 'ERROR')
            return {'success': False, 'error': str(e)}
    
    async def is_connected(self):
        """
        Check if client is connected.
        
        Returns:
            bool: True if connected
        """
        try:
            return self.client.is_connected()
        except:
            return False
    
    async def is_authorized(self):
        """
        Check if client is authorized.
        
        Returns:
            bool: True if authorized
        """
        try:
            return await self.client.is_user_authorized()
        except:
            return False

def get_or_create_client(account_id):
    """
    Get or create a Telegram client for an account.
    
    Args:
        account_id (int): Account ID
        
    Returns:
        TelegramManager: Manager instance or None if account not found
    """
    if account_id in active_clients:
        return active_clients[account_id]
    
    # Get account details from database
    account = get_account(account_id)
    if not account:
        return None
    
    manager = TelegramManager(
        account['api_id'],
        account['api_hash'],
        account['phone_number'],
        account_id
    )
    
    active_clients[account_id] = manager
    return manager

def remove_client(account_id):
    """
    Remove a client from active clients.
    
    Args:
        account_id (int): Account ID
    """
    if account_id in active_clients:
        del active_clients[account_id]
