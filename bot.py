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

# Список актуальных моделей для перебора
MODELS_TO_TRY = [
    'gemini-2.5-flash',
    'gemini-2.0-flash',
    'gemini-1.5-flash'
]

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def ask_gemini(text):
    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=text
            )
            if response.text:
                return response.text
        except Exception as e:
            last_error = e
            print(f"Ошибка с моделью {model_name}: {e}")
            # Если временная перегрузка — даем небольшую паузу
            time.sleep(1)
            continue
            
    # Если ни одна модель не ответила, выводим реальную последнюю ошибку
    raise RuntimeError(f"Все модели не ответили. Последняя ошибка: {last_error}")

@bot.message_handler(content_types=['text'])
def reply(message):
    try:
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
