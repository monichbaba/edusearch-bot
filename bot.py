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

# /search command using Firestore with multi-keyword AND-based match
@bot.message_handler(commands=['search'])
def search_messages(message):
    parts = message.text.strip().split(' ', 1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Jaan, please likho: /search keyword", disable_notification=True)
        return

    keywords = parts[1].strip().lower().split()
    results = []

    messages_ref = db.collection("messages")
    docs = messages_ref.stream()

    for doc in docs:
        data = doc.to_dict()
        text = data.get("text", "").lower()

        if all(kw in text for kw in keywords) and data["text"] not in results:
            results.append(data["text"])
            if len(results) >= 3:
                break

    if results:
        reply = "\n\n".join([f"🔍 Match:\n{r}" for r in results])
        bot.send_message(message.chat.id, reply, disable_notification=True)
    else:
        bot.send_message(message.chat.id, f"Kuch nahi mila for '{parts[1]}', jaan.", disable_notification=True)

# Auto-search with "search" keyword + Firestore + self-match check
@bot.message_handler(func=lambda message: message.chat.id == GROUP_CHAT_ID and message.text and not message.text.startswith('/'))
def auto_search_in_group(message):
    user_text = message.text.strip().lower()

    if "search" not in user_text:
        save_message_to_firestore(message.chat.id, user_text, message.date)
        bot.reply_to(message, f"🔔 Saved & ready for search: '{user_text}'", disable_notification=True)
        return

    keywords = [kw for kw in user_text.split() if kw != "search"]
    results = []

    messages_ref = db.collection("messages")
    docs = messages_ref.stream()

    for doc in docs:
        data = doc.to_dict()
        text = data.get("text", "").lower()

        if text == user_text:
            continue

        if all(kw in text for kw in keywords) and data["text"] not in results:
            results.append(
