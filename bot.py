import json
import firebase_admin
from firebase_admin import credentials, firestore
import telebot
import re
import os
from flask import Flask, request

# 🔐 Setup
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

# 💾 Save + Respond (excluding search command)
def save_and_reply(chat_id, text, timestamp, is_group=False):
    if text.lower().startswith("search "):
        print("🚫 'search' command detected — not saving")
        return

    try:
        db.collection("messages").document().set({
            'chat_id': chat_id,
            'text': text,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        print("✅ Message saved to Firestore:", text[:50])
    except Exception as e:
        print("❌ Firestore save failed:", e)

    tags = generate_tags(text)
    tag_line = f"\n\n📎 Tags: {tags}" if tags else ""
    if is_group:
        try:
            bot.send_message(chat_id, f"🔔 Message saved:\n\n{text[:100]}{tag_line}", disable_notification=True)
        except Exception as e:
            print("❌ Bot reply failed:", e)

# 📩 Channel Handler
@bot.channel_post_handler(func=lambda m: True)
def handle_channel(m):
    print("📡 Received channel message")
    save_and_reply(m.chat.id, m.text, m.date)

# 💬 Group Handler
@bot.message_handler(func=lambda m: m.chat.id == GROUP_CHAT_ID and m.text and not m.text.startswith('/'))
def handle_group(m):
    print("💬 Received group message")
    save_and_reply(m.chat.id, m.text, m.date, is_group=True)

# 📎 /id command
@bot.message_handler(commands=['id'])
def send_id(message):
    bot.send_message(message.chat.id, f"Chat ID: `{message.chat.id}`", parse_mode="Markdown", disable_notification=True)

# 🔍 SEARCH COMMAND HANDLER — DEBUG
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith('search '))
def handle_search(m):
    try:
        keyword = m.text[7:].strip().lower()
        print("🔍 Search command received:", keyword)

        results = db.collection("messages").stream()
        matches = []
        for doc in results:
            data = doc.to_dict()
            text = data.get("text", "")
            if keyword in text.lower():
                matches.append(text)

        print(f"✅ {len(matches)} matches found")

        if matches:
            reply = f"✅ {len(matches)} result(s) found:\n\n" + "\n\n".join(f"• {t[:200]}" for t in matches[:3])
        else:
            reply = f"❌ No results found for: `{keyword}`"

        bot.send_message(m.chat.id, reply, parse_mode="Markdown", disable_notification=True)
    except Exception as e:
        print("❌ handle_search() error:", e)

# 🌐 Flask App
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    print("📥 Webhook received update")
    bot.process_new_updates([update])
    return '', 200

def set_webhook():
    url = f"https://edusearch-bot.onrender.com/{TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=url)
    print(f"🌐 Webhook set to: {url}")

if __name__ == '__main__':
    set_webhook()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
