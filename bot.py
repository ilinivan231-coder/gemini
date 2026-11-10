import os
import threading
from flask import Flask
import telebot
from google import genai

TG_TOKEN = os.environ.get("TG_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

bot = telebot.TeleBot(TG_TOKEN)
client = genai.Client(api_key=GEMINI_KEY)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def get_active_model_name():
    """Динамически находит первую доступную модель для генерации текста"""
    try:
        models = client.models.list()
        for m in models:
            # Ищем модель, которая поддерживает генерацию текста
            actions = getattr(m, 'supported_actions', []) or getattr(m, 'supported_generation_methods', [])
            if 'generateContent' in actions:
                # Убираем префикс 'models/', если он есть
                return m.name.replace('models/', '')
    except Exception as e:
        print(f"Не удалось получить список моделей: {e}")
    # Запасной вариант по умолчанию
    return 'gemini-2.5-flash'

# Находим рабочую модель один раз при запуске
ACTIVE_MODEL = get_active_model_name()
print(f"Используется модель: {ACTIVE_MODEL}")

@bot.message_handler(content_types=['text'])
def reply(message):
    global ACTIVE_MODEL
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        response = client.models.generate_content(
            model=ACTIVE_MODEL,
            contents=message.text
        )
        
        if response.text:
            bot.reply_to(message, response.text)
        else:
            bot.reply_to(message, "Ответ от модели пуст.")
            
    except Exception as e:
        # Если текущая модель выдала сбой, пробуем обновить список
        err_msg = str(e)
        if "404" in err_msg:
            ACTIVE_MODEL = get_active_model_name()
        bot.reply_to(message, f"Ошибка: {e}")

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling(skip_pending=True)
