import json
import firebase_admin
from firebase_admin import credentials, firestore
import telebot
import re
import os
from flask import Flask, request

# Setup
TOKEN = os.environ.get("TOKEN")
firebase_key = json.loads(os.environ.get("FIREBASE_KEY"))
cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred)
db = firestore.client()

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

GROUP_CHAT_ID = -1002549002656
STOPWORDS = {"the", "is", "a", "an", "of", "in", "to", "for", "and", "on", "with", "this", "that", "by", "at", "as"}

# 🔖 Tag Generator
def generate_tags(text):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    unique = list(dict.fromkeys(filtered))
    return " ".join(f"#{w}" for w in unique[:5])

# 💾 Save to Firestore
def save_and_reply(chat_id, text, timestamp, is_group=False):
    db.collection("messages").document().set({
        'chat_id': chat_id,
        'text': text,
        'timestamp': timestamp
    })
    tags = generate_tags(text)
    tag_line = f"\n\n📎 Tags: {tags}" if tags else ""
    if is_group:
        bot.send_message(chat_id, f"🔔 Message saved:{tag_line}", disable_notification=True)
    else:
        print(f"✅ Saved (channel): {text}")

# 🆔 /id command
@bot.message_handler(commands=['id'])
def send_id(message):
    bot.send_message(message.chat.id, f"Chat ID: `{message.chat.id}`", parse_mode="Markdown")

# 📥 Channel post handler
@bot.channel_post_handler(func=lambda m: True)
def handle_channel(m):
    if m.text:
        save_and_reply(m.chat.id, m.text, m.date)

# 📥 Group message handler
@bot.message_handler(func=lambda m: m.chat.id == GROUP_CHAT_ID and m.text and not m.text.startswith('/'))
def handle_group(m):
    if m.text.startswith("search "):
        keyword = m.text.split("search ", 1)[1].strip().lower()
        results = []
        for doc in db.collection("messages").stream():
            content = doc.to_dict()
            if keyword in content.get("text", "").lower():
                results.append(content.get("text"))
        if results:
            reply = "🔎 Found:\n\n" + "\n\n---\n\n".join(results[:5])
        else:
            reply = "❌ No results found."
        bot.send_message(m.chat.id, reply)
    else:
        save_and_reply(m.chat.id, m.text, m.date, is_group=True)

# 🌐 Webhook Setup
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route("/")
def index():
    return "Bot is alive!"

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://edusearch-bot.onrender.com/{TOKEN}")
    print(f"🌐 Webhook set to: https://edusearch-bot.onrender.com/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
