import os
import time
import threading
from flask import Flask
import telebot
from google import genai

# Токены из переменных окружения Render
TG_TOKEN = os.environ.get("TG_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

bot = telebot.TeleBot(TG_TOKEN)
client = genai.Client(api_key=GEMINI_KEY)

MODEL_NAME = 'gemini-3.8-flash'

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def generate_with_retry(prompt, max_retries=3):
    """Отправляет запрос в Gemini. Если сервер перегружен (503), ждет и пробует снова."""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            return response.text
        except Exception as e:
            err_text = str(e)
            # При временной перегрузке (503) делаем паузу и пробуем ещё раз
            if "503" in err_text or "UNAVAILABLE" in err_text:
                if attempt < max_retries - 1:
                    time.sleep(3)  # Ждем 3 секунды перед повтором
                    continue
            raise e

@bot.message_handler(content_types=['text'])
def reply(message):
    if not message.text:
        return
        
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        answer = generate_with_retry(message.text)
        
        if answer:
            bot.reply_to(message, answer)
        else:
            bot.reply_to(message, "Модель вернула пустой ответ.")
            
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # 1. Запуск мини-сервера для Render
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. Запуск приема сообщений Telegram
    print("Бот успешно запущен!")
    bot.infinity_polling(skip_pending=True)
