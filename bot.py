import os
import time
import threading
from flask import Flask
import telebot
from google import genai

TG_TOKEN = os.environ.get("TG_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

bot = telebot.TeleBot(TG_TOKEN)
client = genai.Client(api_key=GEMINI_KEY)

MODEL_NAME = 'gemini-3.8-flash'

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def generate_answer(prompt):
    """Делает запросы к модели и ждет при перегрузке (503)"""
    delays = [2, 5, 8]  # Паузы между попытками в секундах
    last_err = None

    for attempt, delay in enumerate(delays, start=1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            if response.text:
                return response.text
        except Exception as e:
            last_err = e
            err_text = str(e)
            
            # Если сервер временно перегружен (503)
            if "503" in err_text or "UNAVAILABLE" in err_text:
                time.sleep(delay)
                continue
            
            # При любых других ошибках сразу прекращаем
            raise e

    raise last_err

@bot.message_handler(content_types=['text'])
def reply(message):
    if not message.text:
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        answer = generate_answer(message.text)
        bot.reply_to(message, answer)
    except Exception as e:
        err_text = str(e)
        if "503" in err_text or "UNAVAILABLE" in err_text:
            bot.reply_to(
                message,
                "⚠️ Серверы Google Gemini сейчас сильно перегружены (ошибка 503).\n"
                "Пожалуйста, подождите полминуты и попробуйте отправить сообщение снова."
            )
        else:
            bot.reply_to(message, f"Ошибка: {e}")

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот запущен...")
    bot.infinity_polling(skip_pending=True)
