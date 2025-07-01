import json
import firebase_admin
from firebase_admin import credentials, firestore
import telebot
import re
import os
import threading
from flask import Flask

# Bot token
TOKEN = os.environ.get("TOKEN")

# Firebase credentials from environment
firebase_key = json.loads(os.environ.get("FIREBASE_KEY"))
cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred)
db = firestore.client()

# IDs
CHANNEL_USERNAME = "@IcsCoach"
GROUP_CHAT_ID = -1002549002656

bot = telebot.TeleBot(TOKEN)

# 🆔 /id command
@bot.message_handler(commands=['id'])
def send_id(message):
    bot.send_message(
        message.chat.id,
        f"Chat ID: `{message.chat.id}`",
        parse_mode="Markdown",
        disable_notification=True
    )

# 📩 Channel → Save + Auto-unpin
@bot.channel_post_handler(func=lambda message: True)
def handle_channel_post(message):
    if message.text:
        print(f"Channel message: {message.text}")
        save_message_to_firestore(message.chat.id, message.text, message.date)
        try:
            bot.unpin_chat_message(GROUP_CHAT_ID)
        except Exception as e:
            print(f"Unpin failed: {e}")

# 🔍 /search command — multi-keyword AND search
@bot.message_handler(commands=['search'])
def search_messages(message):
    parts = message.text.strip().split(' ', 1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Jaan, please likho: /search keyword", disable_notification=True)
        return

    keywords = parts[1].strip().lower().split()
    results = set()

    messages_ref = db.collection("messages")
    docs = messages_ref.stream()

    for doc in docs:
        data = doc.to_dict()
        text = data.get("text", "").strip()
        text_lower = text.lower()

        if all(kw in text_lower for kw in keywords):
            if text_lower not in results:
                results.add(text_lower)
                bot.send_message(message.chat.id, f"🔍 Match:\n\n{text}", disable_notification=True)
                break

    if not results:
        bot.send_message(message.chat.id, f"Kuch nahi mila for '{parts[1]}', jaan.", disable_notification=True)

# 🤖 Auto-search with keyword + Firestore + Self-match + Clean result
@bot.message_handler(func=lambda message: message.chat.id == GROUP_CHAT_ID and message.text and not message.text.startswith('/'))
def auto_search_in_group(message):
    user_text = message.text.strip().lower()

    if "search" not in user_text:
        save_message_to_firestore(message.chat.id, user_text, message.date)
        bot.reply_to(message, f"🔔 Saved & ready for search: '{user_text}'", disable_notification=True)
        return

    keywords = [kw for kw in user_text.split() if kw != "search"]
    results = set()

    messages_ref = db.collection("messages")
    docs = messages_ref.stream()

    for doc in docs:
        data = doc.to_dict()
        text = data.get("text", "").strip()
        text_lower = text.lower()

        if text_lower == user_text:
            continue

        if all(kw in text_lower for kw in keywords):
            if text_lower not in results:
                results.add(text_lower)
                bot.reply_to(message, f"🔍 Auto-match mila:\n\n{text}", disable_notification=True)
                break  # sirf 1 match dikhaye

    save_message_to_firestore(message.chat.id, user_text, message.date)

    if not results:
        bot.reply_to(message, f"🔔 Saved only (no match): '{user_text}'", disable_notification=True)

# 💾 Firestore Save Function
def save_message_to_firestore(chat_id, text, timestamp):
    doc_ref = db.collection("messages").document()
    doc_ref.set({
        'chat_id': chat_id,
        'text': text,
        'timestamp': timestamp
    })

# 🔁 Run bot in background thread
def run_bot():
    print("🤖 Bot is running...")
    bot.infinity_polling()

# 🌐 Flask app (for Render keep-alive)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

if __name__ == '__main__':
    t = threading.Thread(target=run_bot)
    t.start()
    PORT = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=PORT)
