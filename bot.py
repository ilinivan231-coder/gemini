import os
import time
import threading
from flask import Flask
import telebot
from google import genai

# Токены из переменных окружения
TG_TOKEN = os.environ.get("TG_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

bot = telebot.TeleBot(TG_TOKEN)
client = genai.Client(api_key=GEMINI_KEY)

# Список моделей по приоритету: если 3.8 перегружена, пойдет к следующей
MODELS_TO_TRY = [
    'gemini-3.8-flash',
    'gemini-2.5-flash',
    'gemini-1.5-flash'
]

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def ask_gemini(text):
    """Пытается получить ответ от Gemini с перебором моделей при перегрузке (503)"""
    for model_name in MODELS_TO_TRY:
        for attempt in range(2):  # Делаем до 2 попыток на каждую модель
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=text
                )
                if response.text:
                    return response.text
            except Exception as e:
                err_str = str(e)
                # Если сервер перегружен (503), ждем 2 секунды и пробуем снова/другую модель
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    time.sleep(2)
                    continue
                # Если модель не найдена (404), сразу переходим к следующей модели
                elif "404" in err_str:
                    break
                else:
                    raise e
    raise RuntimeError("Все серверы Gemini сейчас сильно перегружены. Попробуйте через пару минут.")

@bot.message_handler(content_types=['text'])
def reply(message):
    try:
        # Отправляем статус "печатает...", пока ждем ответ
        bot.send_chat_action(message.chat.id, 'typing')
        
        answer = ask_gemini(message.text)
        bot.reply_to(message, answer)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling(skip_pending=True)
