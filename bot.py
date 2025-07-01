import telebot
import re
import os
import threading
from flask import Flask

# Bot token
TOKEN = os.environ.get("TOKEN")

# IDs
CHANNEL_USERNAME = "@IcsCoach"
GROUP_CHAT_ID = -1002549002656

bot = telebot.TeleBot(TOKEN)
saved_messages = []

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
        saved_messages.append(message.text)
        try:
            bot.unpin_chat_message(GROUP_CHAT_ID)
        except Exception as e:
            print(f"Unpin failed: {e}")

# /search command
@bot.message_handler(commands=['search'])
def search_messages(message):
    parts = message.text.strip().split(' ', 1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Jaan, please likho: /search keyword", disable_notification=True)
        return
    keyword = parts[1].strip().lower()
    pattern = re.compile(rf'\b{re.escape(keyword)}\b', re.IGNORECASE)
    for msg in saved_messages:
        if pattern.search(msg):
            bot.send_message(message.chat.id, f"🔍 1 match:\n\n{msg}", disable_notification=True)
            return
    bot.send_message(message.chat.id, f"Kuch nahi mila for '{keyword}', jaan.", disable_notification=True)

# Auto-search in group
@bot.message_handler(func=lambda message: message.chat.id == GROUP_CHAT_ID and message.text and not message.text.startswith('/'))
def auto_search_in_group(message):
    user_text = message.text.strip().lower()
    pattern = re.compile(rf'\b{re.escape(user_text)}\b', re.IGNORECASE)
    for msg in saved_messages:
        if pattern.search(msg):
            bot.reply_to(message, f"🔍 Auto-match mila:\n\n{msg}", disable_notification=True)
            return

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
