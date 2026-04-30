import os
import json
from datetime import datetime
from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'your_verify_token_here')

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token and mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        data = request.get_json()
        print(f"Received webhook: {data}")
        
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
                    print(f"📨 Message from {from_number}: {text}")
    except Exception as e:
        print(f"Error: {e}")
    
    return "OK", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status": "ok"}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
