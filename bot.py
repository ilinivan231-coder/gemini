import os
import threading
from flask import Flask
import telebot
from google import genai

# Подтягиваем переменные окружения
TG_TOKEN = os.environ.get("TG_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

if not TG_TOKEN or not GEMINI_KEY:
    raise ValueError("Отсутствуют обязательные переменные TG_TOKEN или GEMINI_KEY в окружении!")

bot = telebot.TeleBot(TG_TOKEN)
client = genai.Client(api_key=GEMINI_KEY)

# Мини-сервер для поддержания активности на Render / мониторинга
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@bot.message_handler(content_types=['text'])
def reply(message):
    # Пропускаем сообщения без текста
    if not message.text:
        return

    try:
        # Указываем реальную модель Gemini
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=message.text
        )
        
        reply_text = response.text or "Модель вернула пустой ответ (возможно, сработал фильтр безопасности)."
        bot.reply_to(message, reply_text)

    except Exception as e:
        print(f"Error handling message: {e}")
        bot.reply_to(message, f"Произошла ошибка: {e}")

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("Бот запускается...")
    bot.infinity_polling(skip_pending=True)
