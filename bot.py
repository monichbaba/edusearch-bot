import os
import json
import telebot
from flask import Flask, request
from threading import Timer
from time import sleep

# 🔐 Config
TOKEN = os.environ.get("TOKEN") or "YOUR_BOT_TOKEN"
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", -1002549002656))

# 🗂️ Active Poll Tracker
active_polls = {}  # poll_id → {correct, responses, qno}

# 🚀 /start_mcq qset1
@bot.message_handler(commands=['start_mcq'])
def start_mcq(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Usage: /start_mcq qset1")
        return

    filename = f"mcqs/{args[1]}.json"
    if not os.path.exists(filename):
        bot.reply_to(message, f"❌ File not found: {filename}")
        return

    with open(filename, "r", encoding="utf-8") as f:
        questions = json.load(f)

    for i, q in enumerate(questions, start=1):
        question_text = f"🧭 Q{i}:\n{q['question']}"
        sent = bot.send_poll(
            chat_id=GROUP_CHAT_ID,
            question=question_text,
            options=q['options'],
            is_anonymous=False,
            allows_multiple_answers=False
        )
        active_polls[sent.poll.id] = {
            "correct": q["answer_index"],
            "responses": {},
            "qno": i
        }
        Timer(8, lambda pid=sent.poll.id: show_result(pid)).start()
        sleep(10)

# 🧠 Poll Response Tracker
@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    pid = poll_answer.poll_id
    uid = poll_answer.user.id
    selected = poll_answer.option_ids[0]
    if pid in active_polls:
        active_polls[pid]["responses"][uid] = selected

# 📊 Result Formatter
def show_result(pid):
    if pid not in active_polls:
        return
    poll = active_polls[pid]
    correct = poll["correct"]
    responses = poll["responses"]

    sahi = []
    galat = []

    for uid, selected in responses.items():
        try:
            user = bot.get_chat(uid)
            name = user.first_name or f"user_{uid}"
        except:
            name = f"user_{uid}"

        if selected == correct:
            sahi.append(name)
        else:
            galat.append(name)

    qno = poll['qno']
    msg = f"Q{qno} ➤\n"
    if galat:
        msg += f"❌ " + ", ".join(galat) + "\n"
    if sahi:
        msg += f"✅ " + ", ".join(sahi)

    bot.send_message(GROUP_CHAT_ID, msg)
    del active_polls[pid]

# 🌐 Webhook Setup
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "MCQ Bot is alive!"

# 🧠 /id Command (Optional)
@bot.message_handler(commands=['id'])
def send_id(message):
    bot.send_message(message.chat.id, f"Chat ID: `{message.chat.id}`", parse_mode="Markdown")

# 🚀 Start
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://edusearch-bot.onrender.com/{TOKEN}")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
