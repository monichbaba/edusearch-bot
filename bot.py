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

# /id command
@bot.message_handler(commands=['id'])
def send_id(message):
    bot.send_message(
        message.chat.id,
        f"Chat ID: `{message.chat.id}`",
        parse_mode="Markdown",
        disable_notification=True
    )

# Channel → Save + Auto-unpin
@bot.channel_post_handler(func=lambda message: True)
def handle_channel_post(message):
    if message.text:
        print(f"Channel message: {message.text}")
        save_message_to_firestore(message.chat.id, message.text, message.date)
        try:
            bot.unpin_chat_message(GROUP_CHAT_ID)
        except Exception as e:
            print(f"Unpin failed: {e}")

# /search command using Firestore with unique match
@bot.message_handler(commands=['search'])
def search_messages(message):
    parts = message.text.strip().split(' ', 1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Jaan, please likho: /search keyword", disable_notification=True)
        return

    keyword = parts[1].strip().lower()
    results = []

    # 🔍 Firestore query
    messages_ref = db.collection("messages")
    docs = messages_ref.stream()

    for doc in docs:
        data = doc.to_dict()
        text = data.get("text", "").lower()
        if keyword in text and data["text"] not in results:
            results.append(data["text"])
            if len(results) >= 3:
                break  # limit to 3 matches

    if results:
        reply = "\n\n".join([f"🔍 Match:\n{r}" for r in results])
        bot.send_message(message.chat.id, reply, disable_notification=True)
    else:
        bot.send_message(message.chat.id, f"Kuch nahi mila for '{keyword}', jaan.", disable_notification=True)

# Auto-search in group + Save to Firestore
@bot.message_handler(func=lambda message: message.chat.id == GROUP_CHAT_ID and message.text and not message.text.startswith('/'))
def auto_search_in_group(message):
    save_message_to_firestore(message.chat.id, message.text, message.date)
    user_text = message.text.strip().lower()
    bot.reply_to(message, f"🔔 Saved & ready for search: '{user_text}'", disable_notification=True)

# Firestore Save Function
def save_message_to_firestore(chat_id, text, timestamp):
    doc_ref = db.collection("messages").document()
    doc_ref.set({
        'chat_id': chat_id,
        'text': text,
        'timestamp': timestamp
    })

# Run bot in thread
def run_bot():
    print("🤖 Bot is running...")
    bot.infinity_polling()

# Flask app to keep alive on Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

if __name__ == '__main__':
    t = threading.Thread(target=run_bot)
    t.start()
    PORT = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=PORT)
