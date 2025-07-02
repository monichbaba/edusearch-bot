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
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    unique = list(dict.fromkeys(filtered))
    top5 = unique[:5]
    return " ".join(f"#{w}" for w in top5)

# 🔐 Save + Trace Firestore Status
def save_and_reply(chat_id, text, timestamp, is_group=False):
    if text.lower().startswith("search "):
        print("🚫 Skipping Firestore save (search command)")
        return

    print(f"🔥 Trying to save to Firestore → {text}")

    try:
        doc_ref = db.collection("messages").document()
        doc_ref.set({
            'chat_id': chat_id,
            'text': text,
            'timestamp': timestamp
        })
        print(f"✅ Firestore write success: {doc_ref.id}")
    except Exception as e:
        error_msg = f"❌ Firestore Save Failed: {e}"
        print(error_msg)
        if is_group:
            bot.send_message(chat_id, error_msg)
        return

    tags = generate_tags(text)
    tag_line = f"\n\n📎 Tags: {tags}" if tags else ""

    if is_group:
        bot.send_message(chat_id, f"🔔 Message saved.{tag_line}", disable_notification=True)
        bot.send_message(chat_id, "✅ This is a test confirmation message to check bot response.")
    else:
        print(f"✅ Saved (channel): {text}")

# 🔘 /id command
@bot.message_handler(commands=['id'])
def send_id(message):
    bot.send_message(message.chat.id, f"Chat ID: `{message.chat.id}`", parse_mode="Markdown", disable_notification=True)

# 🔘 Channel post handler
@bot.channel_post_handler(func=lambda m: True)
def handle_channel(m):
    if m.text:
        save_and_reply(m.chat.id, m.text, m.date)

# 🔍 Search command like "search xyz"
@bot.message_handler(func=lambda m: m.chat.id == GROUP_CHAT_ID and m.text.lower().startswith("search "))
def handle_search(m):
    keyword = m.text[7:].strip().lower()
    print("🔍 Searching for:", keyword)

    results = []
    try:
        docs = db.collection("messages").stream()
        for doc in docs:
            data = doc.to_dict()
            text = data.get('text', '').lower()
            if keyword in text:
                results.append(data['text'])
    except Exception as e:
        bot.send_message(GROUP_CHAT_ID, f"❌ Search failed: {e}")
        return

    if results:
        reply = "🔍 Results:\n" + "\n\n".join(f"• {r}" for r in results[:5])
    else:
        reply = "❌ No results found."

    bot.send_message(GROUP_CHAT_ID, reply)

# 📨 Group message handler (normal message save)
@bot.message_handler(func=lambda m: m.chat.id == GROUP_CHAT_ID and m.text and not m.text.startswith('/'))
def handle_group(m):
    save_and_reply(m.chat.id, m.text, m.date, is_group=True)

# 🔁 Bot polling thread
def run_bot():
    bot.infinity_polling()

# 🌐 Flask keepalive
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is alive!"

if __name__ == '__main__':
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
