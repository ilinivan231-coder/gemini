import os
import time
import threading
from flask import Flask
import telebot
from openai import OpenAI

TG_TOKEN = os.environ.get("TG_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")

bot = telebot.TeleBot(TG_TOKEN)

ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

# Модель Gemini (можно заменить на 'openai/gpt-4o-mini' или другую)
MODEL_NAME = "google/gemini-2.0-flash-001"

# Словарь для хранения истории сообщений каждого пользователя
user_histories = {}

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running with memory!"

@bot.message_handler(commands=['clear', 'reset', 'start'])
def reset_memory(message):
    """Сброс контекста диалога по команде /clear или /reset"""
    user_id = message.chat.id
    user_histories[user_id] = []
    bot.reply_to(message, "🧹 Память диалога очищена. Начнем с чистого листа!")

@bot.message_handler(content_types=['text'])
def reply(message):
    if not message.text:
        return

    user_id = message.chat.id

    # Инициализируем историю пользователя, если ее еще нет
    if user_id not in user_histories:
        user_histories[user_id] = []

    # Добавляем сообщение пользователя в память
    user_histories[user_id].append({"role": "user", "content": message.text})

    # Ограничиваем историю последними 10 сообщениями, чтобы не превышать лимиты токенов
    if len(user_histories[user_id]) > 10:
        user_histories[user_id] = user_histories[user_id][-10:]

    status_msg = bot.reply_to(message, "⚡ Запрос принят! Формирую ответ...")

    try:
        bot.send_chat_action(message.chat.id, 'typing')

        # Передаем всю сохраненную цепочку сообщений
        completion = ai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=user_histories[user_id]
        )
        
        answer = completion.choices[0].message.content

        # Сохраняем ответ нейросети в историю
        user_histories[user_id].append({"role": "assistant", "content": answer})

        final_text = f"{answer}\n\n---\n🤖 *Модель:* `{MODEL_NAME}`"

        if len(final_text) <= 4000:
            bot.edit_message_text(
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                text=final_text,
                parse_mode="Markdown"
            )
        else:
            bot.delete_message(status_msg.chat.id, status_msg.message_id)
            bot.reply_to(message, final_text, parse_mode="Markdown")

    except Exception as e:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ Ошибка шлюза: {e}"
        )

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.
