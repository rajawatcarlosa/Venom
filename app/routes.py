"""
Flask Routes - Fixed version with proper API credential handling, OTP, and 2FA
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
import asyncio
import os
from datetime import datetime
from app.models import (
    get_all_accounts, get_account, add_account, delete_account,
    get_groups_by_account, update_group_selection, clear_groups_for_account, add_group,
    get_logs, add_log, get_broadcast_history, get_broadcast_stats, get_db
)
from app.telegram_manager import TelegramManager, get_or_create_client, remove_client
from app.broadcast_manager import BroadcastManager
from app.config import Config

# Create blueprints
main_bp = Blueprint('main', __name__, url_prefix='/')
accounts_bp = Blueprint('accounts', __name__, url_prefix='/accounts')
groups_bp = Blueprint('groups', __name__, url_prefix='/groups')
broadcast_bp = Blueprint('broadcast', __name__, url_prefix='/broadcast')
logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

@main_bp.route('/')
def index():
    """Dashboard - Main page"""
    accounts = get_all_accounts()
    active_accounts = len([a for a in accounts if a['status'] == 'authorized'])
    
    total_groups = 0
    for account in accounts:
        groups = get_groups_by_account(account['id'])
        total_groups += len(groups)
    
    stats = get_broadcast_stats()
    total_sent = stats.get('total_sent', 0) or 0
    
    recent_logs = get_logs(limit=10)
    saved_creds = Config.load_credentials()
    
    return render_template('dashboard.html',
                          total_accounts=len(accounts),
                          active_accounts=active_accounts,
                          total_groups=total_groups,
                          total_sent=total_sent,
                          recent_logs=recent_logs,
                          has_saved_creds=saved_creds is not None)

@accounts_bp.route('/')
def list_accounts():
    """Display list of all accounts"""
    accounts = get_all_accounts()
    return render_template('accounts.html', accounts=accounts)

@accounts_bp.route('/setup-credentials', methods=['GET', 'POST'])
def setup_credentials():
    """One-time setup for API credentials"""
    if request.method == 'GET':
        saved_creds = Config.load_credentials()
        return render_template('setup_credentials.html', saved_creds=saved_creds)
    
    try:
        data = request.get_json()
        api_id = data.get('api_id')
        api_hash = data.get('api_hash')
        
        if not api_id or not api_hash:
            return jsonify({'success': False, 'error': 'Missing API credentials'}), 400
        
        Config.save_credentials(api_id, api_hash)
        add_log(None, None, 'API credentials saved successfully')
        
        return jsonify({'success': True, 'message': 'Credentials saved!'})
    except Exception as e:
        add_log(None, None, f'Error saving credentials: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@accounts_bp.route('/add', methods=['GET', 'POST'])
def add_account_page():
    """Add new account"""
    if request.method == 'GET':
        saved_creds = Config.load_credentials()
        return render_template('add_account.html', saved_creds=saved_creds)
    
    try:
        data = request.get_json()
        phone = data.get('phone_number')
        api_id = data.get('api_id')
        api_hash = data.get('api_hash')
        
        if not phone or not api_id or not api_hash:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Check if already exists
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM accounts WHERE phone_number = ?', (phone,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Account already exists'}), 400
        conn.close()
        
        account_id = add_account(phone, int(api_id), api_hash)
        if not account_id:
            return jsonify({'success': False, 'error': 'Failed to create account'}), 500
        
        session['temp_account_id'] = account_id
        session['temp_phone'] = phone
        
        return jsonify({
            'success': True,
            'account_id': account_id,
            'redirect_url': url_for('accounts.send_otp')
        })
        
    except Exception as e:
        add_log(None, None, f'Error adding account: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@accounts_bp.route('/send-otp', methods=['GET', 'POST'])
def send_otp():
    """Send OTP to Telegram"""
    if request.method == 'GET':
        phone = session.get('temp_phone')
        return render_template('send_otp.html', phone=phone)
    
    try:
        account_id = session.get('temp_account_id')
        phone = session.get('temp_phone')
        
        if not account_id or not phone:
            return jsonify({'success': False, 'error': 'Session expired'}), 400
        
        account = get_account(account_id)
        manager = TelegramManager(account['api_id'], account['api_hash'], phone, account_id)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(manager.send_login_code())
            if result['success']:
                add_log(account_id, account_id, f'OTP sent to {phone}')
                return jsonify({'success': True, 'message': 'OTP sent!'})
            else:
                return jsonify({'success': False, 'error': result.get('message')}), 400
        finally:
            loop.close()
            
    except Exception as e:
        add_log(None, None, f'Error: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@accounts_bp.route('/verify-phone', methods=['GET', 'POST'])
def verify_phone():
    """Verify phone with OTP and 2FA support"""
    if request.method == 'GET':
        phone = session.get('temp_phone')
        return render_template('verify_phone.html', phone=phone)
    
    try:
        data = request.get_json()
        verification_code = data.get('code', '').strip()
        password = data.get('password', '').strip()
        account_id = session.get('temp_account_id')
        
        if not account_id:
            return jsonify({'success': False, 'error': 'Session expired'}), 400
        
        account = get_account(account_id)
        manager = TelegramManager(account['api_id'], account['api_hash'], 
                                 account['phone_number'], account_id)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async def get_code():
                return verification_code
            
            async def get_password():
                return password if password else None
            
            result = loop.run_until_complete(
                manager.connect_and_login(verification_callback=get_code, password_callback=get_password)
            )
            
            if result['success']:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('''
                UPDATE accounts SET user_id = ?, first_name = ?, last_name = ?, username = ?, is_bot = ?
                WHERE id = ?
                ''', (result['user_id'], result['first_name'], result['last_name'], 
                      result['username'], result['is_bot'], account_id))
                conn.commit()
                conn.close()
                
                add_log(account_id, account_id, 'Account verified successfully')
                session.pop('temp_account_id', None)
                session.pop('temp_phone', None)
                
                return jsonify({'success': True, 'redirect_url': url_for('accounts.list_accounts')})
            else:
                return jsonify({'success': False, 'error': result.get('message')}), 400
        finally:
            loop.close()
            
    except Exception as e:
        add_log(None, None, f'Error: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@accounts_bp.route('/<int:account_id>/delete', methods=['POST'])
def delete_account_route(account_id):
    """Delete account"""
    try:
        remove_client(account_id)
        if delete_account(account_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Delete failed'}), 500
    except Exception as e:
        add_log(None, None, f'Error: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@groups_bp.route('/')
def list_groups():
    """Group management"""
    accounts = get_all_accounts()
    return render_template('groups.html', accounts=accounts)

@groups_bp.route('/load', methods=['POST'])
def load_groups():
    """Load groups from account"""
    try:
        data = request.get_json()
        account_id = data.get('account_id')
        
        if not account_id:
            return jsonify({'success': False, 'error': 'Account ID required'}), 400
        
        account = get_account(account_id)
        manager = get_or_create_client(account_id)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if not await_sync(manager.is_connected()):
                await_sync(manager.client.connect())
            
            groups = await_sync(manager.get_groups())
            clear_groups_for_account(account_id)
            
            for group in groups:
                add_group(account_id, group['id'], group['name'], 
                         group['type'], group['is_channel'], group['members'])
            
            add_log(account_id, account_id, f'Loaded {len(groups)} groups')
            
            return jsonify({
                'success': True,
                'groups': groups,
                'count': len(groups)
            })
        finally:
            loop.close()
            
    except Exception as e:
        add_log(None, None, f'Error: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@groups_bp.route('/update-selection', methods=['POST'])
def update_selection():
    """Update group selection"""
    try:
        data = request.get_json()
        account_id = data.get('account_id')
        groups = data.get('groups', [])
        
        all_groups = get_groups_by_account(account_id)
        for group in all_groups:
            is_selected = group['group_id'] in groups
            update_group_selection(account_id, group['group_id'], is_selected)
        
        add_log(account_id, account_id, f'Updated {len(groups)} groups')
        return jsonify({'success': True})
        
    except Exception as e:
        add_log(None, None, f'Error: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@groups_bp.route('/get/<int:account_id>')
def get_groups(account_id):
    """Get groups for account"""
    groups = get_groups_by_account(account_id)
    return jsonify({
        'success': True,
        'groups': [dict(g) for g in groups]
    })

@broadcast_bp.route('/')
def broadcast_page():
    """Broadcast page"""
    accounts = get_all_accounts()
    active_broadcasts = BroadcastManager.get_all_broadcasts()
    return render_template('broadcast.html', 
                          accounts=accounts,
                          active_broadcasts=active_broadcasts)

@broadcast_bp.route('/start', methods=['POST'])
def start_broadcast():
    """Start broadcast"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        delay = float(data.get('delay', 1.0))
        auto_repeat = data.get('auto_repeat', False)
        repeat_interval = int(data.get('repeat_interval', 60))
        account_ids = data.get('account_ids', [])
        
        if not message:
            return jsonify({'success': False, 'error': 'Message required'}), 400
        
        session_id = f"broadcast_{int(datetime.now().timestamp() * 1000)}"
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                BroadcastManager.start_broadcast(
                    session_id, message, delay, auto_repeat, repeat_interval, account_ids
                )
            )
            return jsonify(result)
        finally:
            loop.close()
            
    except Exception as e:
        add_log(None, None, f'Error: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@broadcast_bp.route('/<session_id>/stop', methods=['POST'])
def stop_broadcast(session_id):
    """Stop broadcast"""
    try:
        result = BroadcastManager.stop_broadcast(session_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@broadcast_bp.route('/<session_id>/status')
def get_broadcast_status(session_id):
    """Get broadcast status"""
    status = BroadcastManager.get_broadcast_status(session_id)
    if status:
        return jsonify({'success': True, 'status': status})
    return jsonify({'success': False, 'error': 'Not found'}), 404

@logs_bp.route('/')
def logs_page():
    """Logs viewer"""
    logs = get_logs(limit=100)
    return render_template('logs.html', logs=logs)

def await_sync(coro):
    """Run async code synchronously"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)
