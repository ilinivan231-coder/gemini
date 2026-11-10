import os
import threading
from flask import Flask
import telebot
from google import genai

# Получаем токены из настроек Render
TG_TOKEN = os.environ.get("TG_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

bot = telebot.TeleBot(TG_TOKEN)
client = genai.Client(api_key=GEMINI_KEY)

# Сервер-заглушка, чтобы Render не усыплял бота
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

# Обработка входящих текстовых сообщений
@bot.message_handler(content_types=['text'])
def reply(message):
    try:
        # Отправляем текст в Gemini
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=message.text
        )
        
        # Отправляем ответ пользователю в Telegram
        if response.text:
            bot.reply_to(message, response.text)
        else:
            bot.reply_to(message, "Не удалось получить текстовый ответ.")
            
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # 1. Запуск веб-сервера в фоне
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. Запуск приема сообщений
    bot.infinity_polling(skip_pending=True)
