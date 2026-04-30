import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'mySecret123')

# Database setup - runs once when the app starts
def init_db():
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            message TEXT,
            direction TEXT,
            timestamp DATETIME
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Database initialized")

# Call this when the app starts
init_db()

def save_incoming_message(from_number, text):
    """Save incoming message to database"""
    try:
        conn = sqlite3.connect('messages.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO messages (phone, message, direction, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (from_number, text, 'incoming', datetime.now()))
        conn.commit()
        conn.close()
        print(f"💾 Saved message from {from_number} to database")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token and mode == 'subscribe' and token == VERIFY_TOKEN:
        print("✅ Webhook verified!")
        return challenge, 200
    return "Verification failed", 403

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        data = request.get_json()
        print(f"📨 Received webhook: {json.dumps(data, indent=2)}")
        
        # Extract and save message
        entry = data.get('entry', [])
        if entry:
            changes = entry[0].get('changes', [])
            if changes:
                value = changes[0].get('value', {})
                messages = value.get('messages', [])
                if messages:
                    msg = messages[0]
                    from_number = msg.get('from')
                    text = msg.get('text', {}).get('body')
                    
                    print(f"📝 Message from {from_number}: {text}")
                    
                    # 💾 SAVE TO DATABASE - THIS IS THE ADDED LINE
                    save_incoming_message(from_number, text)
                    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return "OK", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status": "ok"}, 200

@app.route('/messages', methods=['GET'])
def get_messages():
    """Optional endpoint to view all messages (for testing)"""
    try:
        conn = sqlite3.connect('messages.db')
        c = conn.cursor()
        c.execute('SELECT id, phone, message, direction, timestamp FROM messages ORDER BY timestamp DESC LIMIT 50')
        rows = c.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            messages.append({
                'id': row[0],
                'phone': row[1],
                'message': row[2],
                'direction': row[3],
                'timestamp': row[4]
            })
        return {"messages": messages}, 200
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
