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

# Если Flash перегружен, пробуем Pro-версию
CANDIDATE_MODELS = [
    'gemini-3.8-flash',
    'gemini-3.8-pro'
]

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def generate_answer(prompt):
    """Перебирает доступные модели и повторяет запрос при ошибке 503."""
    last_exception = None
    
    for model_name in CANDIDATE_MODELS:
        # Пробуем отправить запрос к текущей модели с нарастающей паузой
        for delay in [1, 3]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response.text:
                    return response.text
            except Exception as e:
                last_exception = e
                err_text = str(e)
                # Если перегружен именно сервер (503), ждем и пробуем снова/другую модель
                if "503" in err_text or "UNAVAILABLE" in err_text:
                    time.sleep(delay)
                    continue
                # Если 404 или другая ошибка — сразу идем к следующей модели
                break
                
    raise last_exception

@bot.message_handler(content_types=['text'])
def reply(message):
    if not message.text:
        return
        
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        answer = generate_answer(message.text)
        bot.reply_to(message, answer)
    except Exception as e:
        err_msg = str(e)
        if "503" in err_msg or "UNAVAILABLE" in err_msg:
            bot.reply_to(message, "Серверы Google Gemini сейчас испытывают пиковую нагрузку. Пожалуйста, отправьте сообщение повторно через 10–15 секунд.")
        else:
            bot.reply_to(message, f"Ошибка: {e}")

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот запущен...")
    bot.infinity_polling(skip_pending=True)
