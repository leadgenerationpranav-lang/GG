# server.py
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import os
import hashlib

app = Flask(__name__)
DB_FILE = 'harvester_backend.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT,
            expiry_date TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            message TEXT,
            link TEXT,
            is_active INTEGER DEFAULT 1
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS recharges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            utr_number TEXT,
            status TEXT,
            timestamp TIMESTAMP
        )''')
        
        # Insert a default admin user if not exists (username: admin, password: password123)
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username='admin'")
        if not cur.fetchone():
            pw_hash = hashlib.sha256("password123".encode()).hexdigest()
            future_date = datetime.now() + timedelta(days=30)
            conn.execute("INSERT INTO users (username, password_hash, expiry_date) VALUES (?, ?, ?)",
                         ("admin", pw_hash, future_date))
            
        # Insert a test announcement
        cur.execute("SELECT * FROM announcements")
        if not cur.fetchone():
            conn.execute("INSERT INTO announcements (title, message, link) VALUES (?, ?, ?)",
                         ("🔥 Update v7.1 Available", "Check out our new LinkedIn Scraper tool!", "https://yourwebsite.com"))

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"success": False, "msg": "Missing credentials"}), 400
        
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username=? AND password_hash=?", (username, pw_hash)).fetchone()
        
        if not user:
            return jsonify({"success": False, "msg": "Invalid username or password"}), 401
            
        if not user['is_active']:
            return jsonify({"success": False, "msg": "Account is deactivated"}), 403
            
        expiry = datetime.strptime(user['expiry_date'], '%Y-%m-%d %H:%M:%S.%f')
        if datetime.now() > expiry:
            return jsonify({"success": False, "msg": "Subscription expired. Please recharge."}), 403
            
        return jsonify({
            "success": True, 
            "msg": "Login successful", 
            "expiry": str(expiry.date())
        })

@app.route('/api/announcements', methods=['GET'])
def get_announcements():
    with get_db() as conn:
        ads = conn.execute("SELECT title, message, link FROM announcements WHERE is_active=1 ORDER BY id DESC LIMIT 1").fetchone()
        if ads:
            return jsonify({"success": True, "announcement": dict(ads)})
        return jsonify({"success": False})

@app.route('/api/recharge', methods=['POST'])
def recharge():
    data = request.json
    username = data.get('username')
    utr = data.get('utr_number') # The UPI Transaction ID
    
    # In a real scenario, you would manually verify the UTR from your bank before extending time.
    # For this automated example, we will automatically add 30 days upon submission.
    with get_db() as conn:
        conn.execute("INSERT INTO recharges (username, utr_number, status, timestamp) VALUES (?, ?, ?, ?)",
                     (username, utr, "APPROVED", datetime.now()))
        
        user = conn.execute("SELECT expiry_date FROM users WHERE username=?", (username,)).fetchone()
        if user:
            current_expiry = datetime.strptime(user['expiry_date'], '%Y-%m-%d %H:%M:%S.%f')
            new_expiry = max(current_expiry, datetime.now()) + timedelta(days=30)
            conn.execute("UPDATE users SET expiry_date=? WHERE username=?", (new_expiry, username))
            return jsonify({"success": True, "msg": "Payment verified! Added 30 days."})
            
    return jsonify({"success": False, "msg": "User not found"}), 404

if __name__ == '__main__':
    init_db()
    # Run locally on port 5000
    app.run(host='0.0.0.0', port=5000)