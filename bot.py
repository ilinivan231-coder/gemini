import os
import threading
from flask import Flask
import telebot
from google import genai

# Подтягиваем ключи из настроек сервера
TG_TOKEN = os.environ.get("TG_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

bot = telebot.TeleBot(TG_TOKEN)
client = genai.Client(api_key=GEMINI_KEY)

# Простой мини-сервер, чтобы Render не закрывал процесс
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@bot.message_handler(func=lambda message: True)
def reply(message):
    try:
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=message.text
        )
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # Запускаем фоновый веб-сервер для Render
    threading.Thread(target=run_flask, daemon=True).start()
    # Запускаем прием сообщений из Telegram
    bot.infinity_polling()
