"""
Telegram Manager - Fixed version with proper 2FA and OTP handling
"""

import asyncio
import os
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    FloodWaitError,
    UnauthorizedError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError
)
from telethon.tl.types import Chat, Channel, User
from app.config import Config
from app.models import (
    add_account, update_account_status, get_account, get_account_by_phone,
    add_group, clear_groups_for_account, add_log
)

active_clients = {}

class TelegramManager:
    """Manages Telegram connections"""
    
    def __init__(self, api_id, api_hash, phone_number, account_id=None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.account_id = account_id
        
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
    
    async def send_login_code(self):
        """Send OTP code"""
        try:
            await self.client.connect()
            add_log(self.account_id, self.account_id, f'Connected for {self.phone_number}')
            
            if await self.client.is_user_authorized():
                user = await self.client.get_me()
                return {
                    'success': True,
                    'authorized': True,
                    'user_id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name if user.last_name else '',
                    'username': user.username if user.username else '',
                    'is_bot': user.bot
                }
            
            await self.client.send_code_request(self.phone_number)
            add_log(self.account_id, self.account_id, f'Code sent to {self.phone_number}')
            
            return {'success': True, 'message': 'OTP sent to your Telegram'}
            
        except PhoneNumberInvalidError:
            return {'success': False, 'message': 'Invalid phone. Use +1234567890 format'}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    async def connect_and_login(self, verification_callback=None, password_callback=None):
        """Connect and login with OTP and 2FA"""
        try:
            await self.client.connect()
            add_log(self.account_id, self.account_id, f'Connected for {self.phone_number}')
            
            if await self.client.is_user_authorized():
                user = await self.client.get_me()
                return {
                    'success': True,
                    'user_id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name if user.last_name else '',
                    'username': user.username if user.username else '',
                    'is_bot': user.bot
                }
            
            await self.client.start(
                phone=self.phone_number,
                code_callback=verification_callback,
                password=password_callback
            )
            
            user = await self.client.get_me()
            add_log(self.account_id, self.account_id, f'Login success for {self.phone_number}')
            
            return {
                'success': True,
                'user_id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name if user.last_name else '',
                'username': user.username if user.username else '',
                'is_bot': user.bot
            }
            
        except SessionPasswordNeededError:
            return {'success': False, 'message': '2FA required'}
        except PhoneCodeInvalidError:
            return {'success': False, 'message': 'Invalid OTP code'}
        except Exception as e:
            add_log(self.account_id, self.account_id, f'Error: {str(e)}', 'ERROR')
            return {'success': False, 'message': str(e)}
    
    async def disconnect(self):
        """Disconnect"""
        try:
            await self.client.disconnect()
            add_log(self.account_id, self.account_id, 'Disconnected')
            return True
        except:
            return False
    
    async def get_groups(self):
        """Get all groups/channels"""
        try:
            groups = []
            async for dialog in self.client.iter_dialogs():
                entity = dialog.entity
                
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
            
        except Exception as e:
            add_log(self.account_id, self.account_id, f'Error loading groups: {str(e)}', 'ERROR')
            return []
    
    async def send_message(self, group_id, message, retry_count=0, max_retries=3):
        """Send message to group"""
        try:
            if not message or len(message) > Config.MAX_MESSAGE_LENGTH:
                return {'success': False, 'error': 'invalid_message'}
            
            await self.client.send_message(group_id, message)
            add_log(self.account_id, self.account_id, f'Message sent to {group_id}')
            
            return {'success': True, 'group_id': group_id}
            
        except FloodWaitError as e:
            if retry_count < max_retries:
                await asyncio.sleep(e.seconds)
                return await self.send_message(group_id, message, retry_count + 1, max_retries)
            else:
                return {'success': False, 'error': 'flood_wait'}
        except Exception as e:
            add_log(self.account_id, self.account_id, f'Error: {str(e)}', 'ERROR')
            return {'success': False, 'error': str(e)}
    
    async def is_connected(self):
        """Check if connected"""
        try:
            return self.client.is_connected()
        except:
            return False

def get_or_create_client(account_id):
    """Get or create client"""
    if account_id in active_clients:
        return active_clients[account_id]
    
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
    """Remove client"""
    if account_id in active_clients:
        del active_clients[account_id]
