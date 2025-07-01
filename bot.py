import json
import firebase_admin
from firebase_admin import credentials, firestore
import telebot
from telebot import types
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

# Stopwords
STOPWORDS = {"the", "is", "a", "an", "of", "in", "to", "for", "and", "on", "with", "this", "that", "by", "at", "as"}

# 🔗 Save + Tags + Search Button
def save_and_add_button(chat_id, text, timestamp, is_group=False):
    # Save to Firestore
    db.collection("messages").document().set({
        'chat_id': chat_id,
        'text': text,
        'timestamp': timestamp
    })

    tags = generate_tags(text)
    tag_line = f"\n\n📎 Tags: {tags}" if tags else ""

    if is_group:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔍 Search Something", callback_data="btn_search"))
        bot.send_message(chat_id, f"🔔 Message saved. Use below to search:{tag_line}", reply_markup=markup, disable_notification=True)
    else:
        print(f"✅ Saved (channel): {text}")

# 🏷️ Tag Generator
def generate_tags(text):
    words = re.findall(r'\b\w+\b', text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    unique = list(dict.fromkeys(filtered))
    top5 = unique[:5]
    return " ".join(f"#{w}" for w in top5)

# /id
@bot.message_handler(commands=['id'])
def send_id(message):
    bot.send_message(message.chat.id, f"Chat ID: `{message.chat.id}`", parse_mode="Markdown", disable_notification=True)

# Channel Handler
@bot.channel_post_handler(func=lambda m: True)
def handle_channel(m):
    if m.text:
        save_and_add_button(m.chat.id, m.text, m.date)

# Group Handler
@bot.message_handler(func=lambda m: m.chat.id == GROUP_CHAT_ID and m.text and not m.text.startswith('/'))
def handle_group(m):
    save_and_add_button(m.chat.id, m.text, m.date, is_group=True)

# Button Click
@bot.callback_query_handler(func=lambda c: c.data == "btn_search")
def handle_search_button(c):
    bot.send_message(c.message.chat.id, "Sahab, aap kya search karna chahte hain? Type keyword(s):", reply_to_message_id=c.message.message_id)

# Search Reply
@bot.message_handler(func=lambda m: m.chat.id == GROUP_CHAT_ID and m.text and m.reply_to_message and m.reply_to_message.from_user.is_bot)
def handle_search_reply(m):
    if "Sahab, aap kya search karna chahte hain?" in m.reply_to_message.text:
        keywords = m.text.strip().lower().split()
        results = []
        for doc in db.collection("messages").stream():
            txt = doc.to_dict().get("text", "").lower()
            if all(kw in txt for kw in keywords):
                results.append(doc.to_dict().get("text"))
                if len(results) >= 3:
                    break
        if results:
            bot.reply_to(m, "🔍 Matches found:\n\n" + "\n\n".join(results), disable_notification=True)
        else:
            bot.reply_to(m, f"Kuch nahi mila for '{m.text}', sahab.", disable_notification=True)

# Run
def run_bot():
    bot.infinity_polling()

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is alive!"

if __name__ == '__main__':
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
