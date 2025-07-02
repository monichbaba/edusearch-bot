import json
import firebase_admin
from firebase_admin import credentials, firestore
import telebot
import re
import os
from flask import Flask, request

# ========== 🛠 Setup ==========
print("🚀 Starting EduSearch Bot...")

TOKEN = os.environ.get("TOKEN")
firebase_key = json.loads(os.environ.get("FIREBASE_KEY"))
cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred)
db = firestore.client()

GROUP_CHAT_ID = -1002549002656
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ========== 🧠 Tag Generator ==========
STOPWORDS = {"the", "is", "a", "an", "of", "in", "to", "for", "and", "on", "with", "this", "that", "by", "at", "as"}

def generate_tags(text):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    unique = list(dict.fromkeys(filtered))
    top5 = unique[:5]
    return " ".join(f"#{w}" for w in top5)

# ========== 💾 Save + Debug ==========
def save_and_reply(chat_id, text, timestamp, is_group=False):
    print("📡 save_and_reply() called")
    print(f"🔎 Chat ID: {chat_id}")
    print(f"📝 Message Text: {text}")
    print(f"⏰ Timestamp: {timestamp}")
    
    try:
        db.collection("messages").document().set({
            'chat_id': chat_id,
            'text': text,
            'timestamp': timestamp
        })
        print("✅ Firestore save successful")

        tags = generate_tags(text)
        tag_line = f"\n\n📎 Tags: {tags}" if tags else ""

        if is_group:
            bot.send_message(chat_id, f"🔔 Message saved:\n\n{text}{tag_line}", disable_notification=True)
        else:
            print(f"✅ Saved (channel): {text}")

    except Exception as e:
        print("❌ Firestore save failed:", e)

# ========== 🔧 Command ==========
@bot.message_handler(commands=['id'])
def send_id(message):
    bot.send_message(message.chat.id, f"Chat ID: `{message.chat.id}`", parse_mode="Markdown", disable_notification=True)

# ========== 📥 Handlers ==========
@bot.channel_post_handler(func=lambda m: True)
def handle_channel(m):
    if m.text:
        print("📨 Received message from CHANNEL")
        save_and_reply(m.chat.id, m.text, m.date)

@bot.message_handler(func=lambda m: m.chat.id == GROUP_CHAT_ID and m.text and not m.text.startswith('/'))
def handle_group(m):
    print("👥 Received message in GROUP")
    save_and_reply(m.chat.id, m.text, m.date, is_group=True)

# ========== 🌐 Webhook ==========
WEBHOOK_URL = "https://edusearch-bot.onrender.com"

@app.route(f'/{TOKEN}', methods=['POST'])
def telegram_webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def home():
    return "EduSearch Bot is alive!"

# ========== 🚀 Start ==========
if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    print("🟢 Webhook set at:", f"{WEBHOOK_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
