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

# Список приоритетных рабочих моделей
MODELS_TO_TRY = [
    "google/gemini-2.5-flash",
    "google/gemini-flash-1.5",
    "openai/gpt-4o-mini",
    "google/gemini-2.0-flash-lite-preview:free",
]

user_histories = {}

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running with memory!"

@bot.message_handler(commands=['clear', 'reset', 'start'])
def reset_memory(message):
    user_id = message.chat.id
    user_histories[user_id] = []
    bot.reply_to(message, "🧹 Память диалога очищена. Начнем с чистого листа!")

def request_ai_response(messages):
    """По очереди пробует модели из списка, пока не получит ответ."""
    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            completion = ai_client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            answer = completion.choices[0].message.content
            if answer:
                return answer, model_name
        except Exception as e:
            last_error = e
            print(f"Ошибка с моделью {model_name}: {e}")
            continue
    raise last_error

@bot.message_handler(content_types=['text'])
def reply(message):
    if not message.text:
        return

    user_id = message.chat.id

    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "content": message.text})

    if len(user_histories[user_id]) > 10:
        user_histories[user_id] = user_histories[user_id][-10:]

    status_msg = bot.reply_to(message, "⚡ Запрос принят! Формирую ответ...")

    try:
        bot.send_chat_action(message.chat.id, 'typing')

        answer, used_model = request_ai_response(user_histories[user_id])
        user_histories[user_id].append({"role": "assistant", "content": answer})

        final_text = f"{answer}\n\n---\n🤖 *Модель:* `{used_model}`"

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
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот запускается...")

    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception as e:
        print(f"Ошибка сброса вебхука: {e}")

    bot.infinity_polling(skip_pending=True)
