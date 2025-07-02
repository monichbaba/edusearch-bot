import json
import firebase_admin
from firebase_admin import credentials, firestore
import telebot
import re
import os
import threading
from flask import Flask

# Setup
TOKEN = os.environ.get("TOKEN")
firebase_key = json.loads(os.environ.get("FIREBASE_KEY"))
cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred)
db = firestore.client()

GROUP_CHAT_ID = -1002549002656
bot = telebot.TeleBot(TOKEN)

STOPWORDS = {"the", "is", "a", "an", "of", "in", "to", "for", "and", "on", "with", "this", "that", "by", "at", "as"}

# 🏷️ Tag Generator
def generate_tags(text):
    words = re.findall(r'\b[a-zA-Z\u0900-\u097F]{3,}\b', text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    unique = list(dict.fromkeys(filtered))
    top5 = unique[:5]
    return " ".join(f"#{w}" for w in top5)

# 🔐 Save + 📎 Tags
def save_and_reply(chat_id, text, timestamp, is_group=False):
    print("📡 save_and_reply() called")
    try:
        db.collection("messages").document().set({
            'chat_id': chat_id,
            'text': text,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        print("✅ Firestore save successful")
    except Exception as e:
        print(f"❌ Firestore save failed: {e}")
        return

    tags = generate_tags(text)
    tag_line = f"\n\n📎 Tags: {tags}" if tags else ""
    if is_group:
        try:
            bot.send_message(chat_id, f"🔔 Message saved:\n\n{text[:100]}{tag_line}", disable_notification=True)
        except Exception as e:
            print(f"❌ bot.send_message failed: {e}")
    else:
        print(f"✅ Saved (channel): {text[:100]}")

# /id command
@bot.message_handler(commands=['id'])
def send_id(message):
    bot.send_message(message.chat.id, f"Chat ID: `{message.chat.id}`", parse_mode="Markdown", disable_notification=True)

# CHANNEL handler
@bot.channel_post_handler(func=lambda m: True)
def handle_channel(m):
    print("📩 CHANNEL handler activated")
    print("📨 Channel Message:", m.text)
    save_and_reply(m.chat.id, m.text, m.date)

# GROUP handler
@bot.message_handler(func=lambda m: m.chat.id == GROUP_CHAT_ID and m.text and not m.text.startswith('/'))
def handle_group(m):
    print("💬 GROUP handler activated")
    print("📨 Group Message:", m.text)
    save_and_reply(m.chat.id, m.text, m.date, is_group=True)

# Bot polling
def run_bot():
    print("🚀 Bot polling started")
    bot.infinity_polling()

# Flask server (keepalive)
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is alive!"

if __name__ == '__main__':
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
