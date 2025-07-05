import os
import json
import telebot
from flask import Flask, request
from threading import Timer
from time import sleep
from datetime import datetime

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

    sent_poll_ids = []  # Store poll message IDs for later deletion

    for i, q in enumerate(questions, start=1):
        question_text = f"🧭 Q{i}:\n{q['q']}"
        sent = bot.send_poll(
            chat_id=GROUP_CHAT_ID,
            question=question_text,
            options=q['options'],
            is_anonymous=False,
            allows_multiple_answers=False
        )
        sent_poll_ids.append(sent.message_id)

        active_polls[sent.poll.id] = {
            "correct": q["answer_index"],
            "responses": {},
            "qno": i
        }

        Timer(8, lambda pid=sent.poll.id: show_result(pid)).start()
        sleep(10)

    # ⏲️ Auto delete all polls and send final message after 60 mins
    def delete_all_polls():
        for mid in sent_poll_ids:
            try:
                bot.delete_message(chat_id=GROUP_CHAT_ID, message_id=mid)
            except:
                pass

        now = datetime.now().strftime("%I:%M %p").lstrip("0")
        msg = f"🧠 Test completed at {now}. Come tomorrow at 8:00 PM."
        bot.send_message(GROUP_CHAT_ID, msg)

    Timer(3600, delete_all_polls).start()

# 🧠 Poll Response Tracker
@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    pid = poll_answer.poll_id
    uid = poll_answer.user.id
    selected = poll_answer.option_ids[0]
    if pid in active_polls:
        active_polls[pid]["responses"][uid] = selected

# 📊 Result Formatter (❌ Only Wrong Users)
def show_result(pid):
    if pid not in active_polls:
        return
    poll = active_polls[pid]
    correct = poll["correct"]
    responses = poll["responses"]

    galat = []

    for uid, selected in responses.items():
        try:
            user = bot.get_chat(uid)
            name = user.first_name or f"user_{uid}"
        except:
            name = f"user_{uid}"

        if selected != correct:
            galat.append(name)

    qno = poll['qno']
    if galat:
        msg = f"Q{qno} ➤\n❌ " + ", ".join(galat)
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
