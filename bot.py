import os
import time
import threading
from flask import Flask
import telebot
from telebot import types
from openai import OpenAI

TG_TOKEN = os.environ.get("TG_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")

bot = telebot.TeleBot(TG_TOKEN)

ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

MODELS = {
    "1": ("✨ Gemini 2.5 Flash", "google/gemini-2.5-flash"),
    "2": ("🟢 ChatGPT 4o-mini", "openai/gpt-4o-mini"),
    "3": ("🎁 Gemini Lite (Free)", "google/gemini-2.0-flash-lite-preview:free"),
    "4": ("🦙 Llama 3.2 (Free)", "meta-llama/llama-3.2-3b-instruct:free")
}

DEFAULT_MODEL = "google/gemini-2.5-flash"

user_models = {}
user_histories = {}

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def build_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key, val in MODELS.items():
        name, slug = val
        btn = types.InlineKeyboardButton(text=name, callback_data="m_" + key)
        kb.add(btn)
    return kb

@bot.message_handler(commands=['model', 'models'])
def cmd_model(message):
    uid = message.chat.id
    current = user_models.get(uid, DEFAULT_MODEL)
    text = "🤖 Текущая модель:\n" + current + "\n\nВыберите модель:"
    bot.reply_to(message, text, reply_markup=build_keyboard())

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("m_"))
def on_model_click(call):
    key = call.data.replace("m_", "")
    if key in MODELS:
        name, slug = MODELS[key]
        user_models[call.message.chat.id] = slug
        bot.answer_callback_query(call.id, "Выбрано: " + name)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✅ Активная модель:\n" + slug
        )

@bot.message_handler(commands=['clear', 'reset', 'start'])
def cmd_reset(message):
    uid = message.chat.id
    user_histories[uid] = []
    current = user_models.get(uid, DEFAULT_MODEL)
    text = "🧹 Память очищена.\nМодель: " + current + "\nСменить модель: /model"
    bot.reply_to(message, text)

@bot.message_handler(content_types=['text'])
def on_message(message):
    if not message.text:
        return

    uid = message.chat.id
    model = user_models.get(uid, DEFAULT_MODEL)

    if uid not in user_histories:
        user_histories[uid] = []

    user_histories[uid].append({"role": "user", "content": message.text})

    if len(user_histories[uid]) > 10:
        user_histories[uid] = user_histories[uid][-10:]

    status_msg = bot.reply_to(message, "⚡ Запрос обрабатывается (" + model + ")...")

    try:
        bot.send_chat_action(uid, 'typing')

        resp = ai_client.chat.completions.create(
            model=model,
            messages=user_histories[uid],
            max_tokens=1500
        )

        answer = resp.choices[0].message.content
        user_histories[uid].append({"role": "assistant", "content": answer})

        final_text = answer + "\n\n---\n🤖 Модель: " + model

        if len(final_text) <= 4000:
            bot.edit_message_text(
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                text=final_text
            )
        else:
            bot.delete_message(status_msg.chat.id, status_msg.message_id)
            bot.reply_to(message, final_text)

    except Exception as e:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text="❌ Ошибка: " + str(e)
        )

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот запускается...")

    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass

    bot.infinity_polling(skip_pending=True)
