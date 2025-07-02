import os
import re
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request
import telebot

# ✅ Load env vars
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Optional, if needed

# ✅ Initialize Telegram bot
bot = telebot.TeleBot(BOT_TOKEN)

# ✅ Firebase setup
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ✅ Flask app
app = Flask(__name__)

# ✅ Extract #tags from message
def extract_tags(text):
    return re.findall(r"#\w+", text)

# ✅ Firestore save
def save_to_firestore(chat_id, user_name, message_text, tags):
    db.collection("messages").add({
        "chat_id": chat_id,
        "user_name": user_name,
        "message": message_text,
        "tags": tags,
    })

# ✅ Count Firestore messages
def count_messages():
    return len(list(db.collection("messages").stream()))

# ✅ Get latest Firestore messages
def get_latest_messages(n=5):
    docs = db.collection("messages").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(n).stream()
    return [doc.to_dict() for doc in docs]

# ✅ Clear all Firestore messages
def clear_messages():
    docs = db.collection("messages").stream()
    for doc in docs:
        db.collection("messages").document(doc.id).delete()

# ✅ Command parser
def command_handler(text):
    text = text.strip().lower()

    if text == "/count":
        count = count_messages()
        return f"📊 Total messages saved: {count}"

    elif text == "/latest":
        latest = get_latest_messages()
        if not latest:
            return "📭 No messages found."
        reply = "🕑 Latest messages:\n"
        for msg in latest:
            reply += f"- {msg.get('user_name', 'User')}: {msg.get('message', '')}\n"
        return reply

    elif text == "/clear":
        clear_messages()
        return "🧹 All messages cleared."

    else:
        return "❓ Unknown command."

# ✅ Main handler for all messages
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    message_text = message.text

    if message_text.startswith("/"):
        response = command_handler(message_text)
        print(f"📤 Replying to command: {message_text}")
        bot.send_message(chat_id, response)
        return

    tags = extract_tags(message_text)
    save_to_firestore(chat_id, user_name, message_text, tags)

    tag_line = f"\n\n📎 Tags: {' '.join(tags)}" if tags else ""
    print("📤 Reply bhejne ki koshish ho rahi hai...")
    bot.send_message(chat_id, f"🔔 Message saved:{tag_line}", disable_notification=False)

# ✅ Webhook receiver
@app.route("/", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# ✅ Render health check route
@app.route("/")
def index():
    return "Bot is alive!"

# ✅ Run with webhook setup
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://edusearch-bot.onrender.com/{BOT_TOKEN}")
    print(f"🌐 Webhook set to: https://edusearch-bot.onrender.com/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
