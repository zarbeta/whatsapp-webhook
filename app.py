import os
import json
import requests
import sqlite3
import mysql.connector
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# ============================================================
# CONFIGURATION (Set these as environment variables in Render)
# ============================================================
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'WA_POC_2026_SECRET')
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')  # Your System User token
PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID', '1120673667794229')
N8N_WEBHOOK_URL = os.environ.get('N8N_WEBHOOK_URL')  # ngrok URL for n8n

# Database type: 'mysql' or 'sqlite'
DB_TYPE = os.environ.get('DB_TYPE', 'sqlite')  # Use 'mysql' for production

# MySQL config (if using MySQL)
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'whatsapp_bot')

# ============================================================
# DATABASE SETUP
# ============================================================
def init_db():
    """Initialize database tables"""
    if DB_TYPE == 'mysql':
        init_mysql()
    else:
        init_sqlite()

def init_mysql():
    """Initialize MySQL tables"""
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        cursor = conn.cursor()
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message_id VARCHAR(255) NULL,
                phone VARCHAR(20) NOT NULL,
                name VARCHAR(255) NULL,
                message TEXT NOT NULL,
                direction ENUM('inbound', 'outbound') NOT NULL,
                service_type ENUM('cleaning', 'landscape', 'pestcontrol') NULL,
                address TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_phone (phone),
                INDEX idx_created_at (created_at)
            )
        ''')
        
        # Conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                phone VARCHAR(20) PRIMARY KEY,
                current_step VARCHAR(50) NULL,
                collected_address TEXT NULL,
                collected_phone VARCHAR(20) NULL,
                collected_name VARCHAR(255) NULL,
                service_type VARCHAR(50) NULL,
                last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_last_message_at (last_message_at)
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ MySQL database initialized")
    except Exception as e:
        print(f"❌ MySQL init error: {e}")

def init_sqlite():
    """Initialize SQLite tables"""
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    
    # Messages table
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT,
            phone TEXT NOT NULL,
            name TEXT,
            message TEXT NOT NULL,
            direction TEXT NOT NULL,
            service_type TEXT,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Conversations table
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            phone TEXT PRIMARY KEY,
            current_step TEXT,
            collected_address TEXT,
            collected_phone TEXT,
            collected_name TEXT,
            service_type TEXT,
            last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ SQLite database initialized")

def get_db_connection():
    """Get database connection"""
    if DB_TYPE == 'mysql':
        return mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
    else:
        return sqlite3.connect('messages.db')

# Initialize database on startup
init_db()

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def save_incoming_message(from_number, text, name=None, message_id=None):
    """Save incoming message to database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == 'mysql':
            cursor.execute('''
                INSERT INTO messages (message_id, phone, name, message, direction, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (message_id, from_number, name, text, 'inbound', datetime.now()))
        else:
            cursor.execute('''
                INSERT INTO messages (message_id, phone, name, message, direction, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (message_id, from_number, name, text, 'inbound', datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"💾 Saved inbound message from {from_number}")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def save_outbound_message(to_number, text):
    """Save outgoing message to database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == 'mysql':
            cursor.execute('''
                INSERT INTO messages (phone, message, direction, created_at)
                VALUES (%s, %s, %s, %s)
            ''', (to_number, text, 'outbound', datetime.now()))
        else:
            cursor.execute('''
                INSERT INTO messages (phone, message, direction, created_at)
                VALUES (?, ?, ?, ?)
            ''', (to_number, text, 'outbound', datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def update_conversation(phone, message):
    """Update conversation state (for tracking multi-turn dialogs)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if conversation exists
        if DB_TYPE == 'mysql':
            cursor.execute('SELECT phone FROM conversations WHERE phone = %s', (phone,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute('''
                    UPDATE conversations 
                    SET last_message_at = %s, updated_at = %s
                    WHERE phone = %s
                ''', (datetime.now(), datetime.now(), phone))
            else:
                cursor.execute('''
                    INSERT INTO conversations (phone, last_message_at, created_at, updated_at)
                    VALUES (%s, %s, %s, %s)
                ''', (phone, datetime.now(), datetime.now(), datetime.now()))
        else:
            cursor.execute('SELECT phone FROM conversations WHERE phone = ?', (phone,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute('''
                    UPDATE conversations 
                    SET last_message_at = ?, updated_at = ?
                    WHERE phone = ?
                ''', (datetime.now(), datetime.now(), phone))
            else:
                cursor.execute('''
                    INSERT INTO conversations (phone, last_message_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (phone, datetime.now(), datetime.now(), datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Conversation update error: {e}")
        return False

# ============================================================
# WEBHOOK ENDPOINTS
# ============================================================
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Meta webhook verification"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token and mode == 'subscribe' and token == VERIFY_TOKEN:
        print("✅ Webhook verified!")
        return challenge, 200
    return "Verification failed", 403

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Receive WhatsApp messages and forward to n8n"""
    try:
        data = request.get_json()
        print(f"📨 Received webhook: {json.dumps(data, indent=2)}")
        
        # Extract message
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
                    message_id = msg.get('id')
                    
                    # Get contact name if available
                    contacts = value.get('contacts', [])
                    name = contacts[0].get('profile', {}).get('name') if contacts else None
                    
                    print(f"📝 Message from {from_number}: {text}")
                    
                    # Save to database
                    save_incoming_message(from_number, text, name, message_id)
                    
                    # Update conversation tracking
                    update_conversation(from_number, text)
                    
                    # Forward to n8n webhook
                    if N8N_WEBHOOK_URL:
                        try:
                            forward_data = {
                                "from": from_number,
                                "message": text,
                                "name": name,
                                "timestamp": datetime.now().isoformat()
                            }
                            response = requests.post(N8N_WEBHOOK_URL, json=forward_data, timeout=5)
                            print(f"✅ Forwarded to n8n: {response.status_code}")
                        except Exception as e:
                            print(f"❌ Forward error: {e}")
                    
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
    
    return "OK", 200

@app.route('/send', methods=['POST'])
def send_message():
    """Receive reply from n8n and send to WhatsApp"""
    try:
        data = request.get_json()
        to_number = data.get('to')
        message_text = data.get('text')
        
        if not to_number or not message_text:
            return jsonify({"error": "Missing 'to' or 'text' field"}), 400
        
        # Call Meta WhatsApp API
        url = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message_text}
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        # Save outbound message to database
        if response.status_code == 200:
            save_outbound_message(to_number, message_text)
            print(f"✅ Sent message to {to_number}: {message_text}")
        else:
            print(f"❌ Send failed: {response.text}")
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# UTILITY ENDPOINTS
# ============================================================
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for Render"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/messages', methods=['GET'])
def get_messages():
    """View recent messages (for testing)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == 'mysql':
            cursor.execute('SELECT id, phone, message, direction, created_at FROM messages ORDER BY created_at DESC LIMIT 50')
        else:
            cursor.execute('SELECT id, phone, message, direction, created_at FROM messages ORDER BY created_at DESC LIMIT 50')
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        messages = []
        for row in rows:
            messages.append({
                'id': row[0],
                'phone': row[1],
                'message': row[2],
                'direction': row[3],
                'timestamp': str(row[4])
            })
        return jsonify({"messages": messages}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/conversations', methods=['GET'])
def get_conversations():
    """View active conversations (for testing)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == 'mysql':
            cursor.execute('SELECT phone, current_step, service_type, last_message_at FROM conversations ORDER BY last_message_at DESC')
        else:
            cursor.execute('SELECT phone, current_step, service_type, last_message_at FROM conversations ORDER BY last_message_at DESC')
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        conversations = []
        for row in rows:
            conversations.append({
                'phone': row[0],
                'current_step': row[1],
                'service_type': row[2],
                'last_message_at': str(row[3])
            })
        return jsonify({"conversations": conversations}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def root():
    """Root endpoint"""
    return jsonify({
        "service": "WhatsApp Webhook Server",
        "status": "running",
        "endpoints": {
            "GET /webhook": "Meta verification",
            "POST /webhook": "Receive WhatsApp messages",
            "POST /send": "Send WhatsApp messages (for n8n)",
            "GET /health": "Health check",
            "GET /messages": "View recent messages",
            "GET /conversations": "View active conversations"
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)