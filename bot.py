import os
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

# Список надежных бесплатных моделей OpenRouter по приоритету
FREE_MODELS = [
    "google/gemini-2.0-flash-lite-preview:free",
    "meta-llama/llama-3.3-70b-instruct:free"
]

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running via OpenRouter!"

def get_ai_response(text):
    """Опрашивает бесплатные модели по очереди на случай отключения одной из них"""
    last_error = None
    for model_name in FREE_MODELS:
        try:
            completion = ai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": text}
                ]
            )
            return completion.choices[0].message.content
        except Exception as e:
            last_error = e
            print(f"Ошибка с моделью {model_name}: {e}")
            continue
    raise last_error

@bot.message_handler(content_types=['text'])
def reply(message):
    if not message.text:
        return

    status_msg = bot.reply_to(message, "⚡ Запрос принят! Формирую ответ...")

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        answer = get_ai_response(message.text)

        if len(answer) <= 4000:
            bot.edit_message_text(
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                text=answer
            )
        else:
            bot.delete_message(status_msg.chat.id, status_msg.message_id)
            bot.reply_to(message, answer)

    except Exception as e:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ Ошибка шлюза: {e}"
        )

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот успешно запущен!")
    bot.infinity_polling(skip_pending=True)
