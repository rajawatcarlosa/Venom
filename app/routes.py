"""
Flask Routes
Defines all URL routes and view functions for the web application.
Handles requests for accounts, groups, broadcasts, and logs.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
import asyncio
import os
from datetime import datetime
from app.models import (
    get_all_accounts, get_account, add_account, delete_account,
    get_groups_by_account, update_group_selection, clear_groups_for_account, add_group,
    get_logs, add_log, get_broadcast_history, get_broadcast_stats
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

# ==================== Main Routes ====================

@main_bp.route('/')
def index():
    """
    Dashboard - Main page showing application statistics.
    """
    accounts = get_all_accounts()
    active_accounts = len([a for a in accounts if a['status'] == 'authorized'])
    
    total_groups = 0
    for account in accounts:
        groups = get_groups_by_account(account['id'])
        total_groups += len(groups)
    
    stats = get_broadcast_stats()
    total_sent = stats.get('total_sent', 0) or 0
    
    # Get recent logs
    recent_logs = get_logs(limit=10)
    
    return render_template('dashboard.html',
                          total_accounts=len(accounts),
                          active_accounts=active_accounts,
                          total_groups=total_groups,
                          total_sent=total_sent,
                          recent_logs=recent_logs)

# ==================== Account Routes ====================

@accounts_bp.route('/')
def list_accounts():
    """
    Display list of all accounts.
    """
    accounts = get_all_accounts()
    return render_template('accounts.html', accounts=accounts)

@accounts_bp.route('/add', methods=['GET', 'POST'])
def add_account_page():
    """
    Add new account page and handler.
    """
    if request.method == 'GET':
        return render_template('add_account.html')
    
    try:
        data = request.get_json()
        phone = data.get('phone_number')
        api_id = data.get('api_id')
        api_hash = data.get('api_hash')
        
        # Validate inputs
        if not phone or not api_id or not api_hash:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Check if account already exists
        existing = get_account(phone)
        if existing:
            return jsonify({'success': False, 'error': 'Account already exists'}), 400
        
        # Create temporary account entry
        account_id = add_account(phone, api_id, api_hash)
        if not account_id:
            return jsonify({'success': False, 'error': 'Failed to create account'}), 500
        
        session['temp_account_id'] = account_id
        session['temp_phone'] = phone
        
        return jsonify({
            'success': True,
            'account_id': account_id,
            'redirect_url': url_for('accounts.verify_phone')
        })
        
    except Exception as e:
        add_log(None, None, f'Error adding account: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@accounts_bp.route('/verify-phone', methods=['GET', 'POST'])
def verify_phone():
    """
    Phone verification page.
    """
    if request.method == 'GET':
        phone = session.get('temp_phone')
        return render_template('verify_phone.html', phone=phone)
    
    try:
        data = request.get_json()
        verification_code = data.get('code')
        account_id = session.get('temp_account_id')
        
        if not account_id:
            return jsonify({'success': False, 'error': 'Session expired'}), 400
        
        account = get_account(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        # Create and connect client
        manager = TelegramManager(account['api_id'], account['api_hash'], 
                                 account['phone_number'], account_id)
        
        # Run async login
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Store verification code for client to use
            async def get_code():
                return verification_code
            
            result = loop.run_until_complete(
                manager.connect_and_login(verification_callback=get_code)
            )
            
            if result['success']:
                # Update account with user info
                from app.models import get_db
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
        add_log(None, None, f'Error verifying phone: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@accounts_bp.route('/<int:account_id>/delete', methods=['POST'])
def delete_account_route(account_id):
    """
    Delete an account.
    """
    try:
        # Remove active client
        remove_client(account_id)
        
        # Delete from database
        if delete_account(account_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Delete failed'}), 500
            
    except Exception as e:
        add_log(None, None, f'Error deleting account: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@accounts_bp.route('/<int:account_id>/status')
def get_account_status(account_id):
    """
    Get account status.
    """
    account = get_account(account_id)
    if not account:
        return jsonify({'success': False, 'error': 'Account not found'}), 404
    
    return jsonify({
        'success': True,
        'account': dict(account)
    })

# ==================== Group Routes ====================

@groups_bp.route('/')
def list_groups():
    """
    Group management page.
    """
    accounts = get_all_accounts()
    return render_template('groups.html', accounts=accounts)

@groups_bp.route('/load', methods=['POST'])
def load_groups():
    """
    Load groups from a Telegram account.
    """
    try:
        data = request.get_json()
        account_id = data.get('account_id')
        
        if not account_id:
            return jsonify({'success': False, 'error': 'Account ID required'}), 400
        
        account = get_account(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        # Get or create client
        manager = get_or_create_client(account_id)
        if not manager:
            return jsonify({'success': False, 'error': 'Failed to create client'}), 500
        
        # Load groups
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Connect if needed
            if not await_sync(manager.is_connected()):
                await_sync(manager.client.connect())
            
            # Get groups
            groups = await_sync(manager.get_groups())
            
            # Clear old groups and save new ones
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
        add_log(None, None, f'Error loading groups: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@groups_bp.route('/update-selection', methods=['POST'])
def update_selection():
    """
    Update group selection for broadcast.
    """
    try:
        data = request.get_json()
        account_id = data.get('account_id')
        groups = data.get('groups', [])
        
        if not account_id:
            return jsonify({'success': False, 'error': 'Account ID required'}), 400
        
        # Get all groups for this account
        all_groups = get_groups_by_account(account_id)
        
        # Update each group
        for group in all_groups:
            is_selected = group['group_id'] in groups
            update_group_selection(account_id, group['group_id'], is_selected)
        
        add_log(account_id, account_id, f'Updated group selection: {len(groups)} groups selected')
        
        return jsonify({'success': True})
        
    except Exception as e:
        add_log(None, None, f'Error updating selection: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@groups_bp.route('/get/<int:account_id>')
def get_groups(account_id):
    """
    Get groups for an account.
    """
    groups = get_groups_by_account(account_id)
    return jsonify({
        'success': True,
        'groups': [dict(g) for g in groups]
    })

# ==================== Broadcast Routes ====================

@broadcast_bp.route('/')
def broadcast_page():
    """
    Broadcast page.
    """
    accounts = get_all_accounts()
    active_broadcasts = BroadcastManager.get_all_broadcasts()
    return render_template('broadcast.html', 
                          accounts=accounts,
                          active_broadcasts=active_broadcasts)

@broadcast_bp.route('/start', methods=['POST'])
def start_broadcast():
    """
    Start a new broadcast.
    """
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        delay = float(data.get('delay', 1.0))
        auto_repeat = data.get('auto_repeat', False)
        repeat_interval = int(data.get('repeat_interval', 60))
        account_ids = data.get('account_ids', [])
        
        # Validation
        if not message:
            return jsonify({'success': False, 'error': 'Message required'}), 400
        
        if len(message) > Config.MAX_MESSAGE_LENGTH:
            return jsonify({'success': False, 'error': f'Message too long (max {Config.MAX_MESSAGE_LENGTH})'}), 400
        
        if delay < Config.MIN_BROADCAST_DELAY or delay > Config.MAX_BROADCAST_DELAY:
            return jsonify({'success': False, 'error': f'Delay must be between {Config.MIN_BROADCAST_DELAY} and {Config.MAX_BROADCAST_DELAY}'}), 400
        
        # Generate session ID
        session_id = f"broadcast_{int(datetime.now().timestamp() * 1000)}"
        
        # Start broadcast
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
        add_log(None, None, f'Broadcast error: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@broadcast_bp.route('/<session_id>/stop', methods=['POST'])
def stop_broadcast(session_id):
    """
    Stop a broadcast.
    """
    try:
        result = BroadcastManager.stop_broadcast(session_id)
        return jsonify(result)
    except Exception as e:
        add_log(None, None, f'Error stopping broadcast: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500

@broadcast_bp.route('/<session_id>/status')
def get_broadcast_status(session_id):
    """
    Get broadcast status.
    """
    status = BroadcastManager.get_broadcast_status(session_id)
    if status:
        return jsonify({'success': True, 'status': status})
    else:
        return jsonify({'success': False, 'error': 'Session not found'}), 404

@broadcast_bp.route('/history')
def broadcast_history():
    """
    Get broadcast history.
    """
    account_id = request.args.get('account_id', type=int)
    limit = request.args.get('limit', 50, type=int)
    
    history = get_broadcast_history(account_id, limit)
    return jsonify({
        'success': True,
        'history': [dict(h) for h in history]
    })

# ==================== Logs Routes ====================

@logs_bp.route('/')
def logs_page():
    """
    Logs viewer page.
    """
    logs = get_logs(limit=100)
    return render_template('logs.html', logs=logs)

@logs_bp.route('/get')
def get_logs_api():
    """
    Get logs via API.
    """
    limit = request.args.get('limit', 100, type=int)
    account_id = request.args.get('account_id', type=int)
    
    from app.models import get_logs_by_account
    
    if account_id:
        logs = get_logs_by_account(account_id, limit)
    else:
        logs = get_logs(limit)
    
    return jsonify({
        'success': True,
        'logs': [dict(l) for l in logs]
    })

# ==================== Helper Functions ====================

def await_sync(coro):
    """
    Helper to run async code synchronously.
    
    Args:
        coro: Coroutine to run
        
    Returns:
        Result of coroutine
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)
