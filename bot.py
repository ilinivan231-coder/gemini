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

def generate_with_infinite_retry(prompt, status_msg):
    """
    Отправляет запрос в Gemini. 
    При ошибке 503 пересчитывает таймер, редактирует сообщение в Telegram и ждет.
    """
    # Список пауз (в секундах) перед каждой повторной попыткой: всего до ~2-3 минут
    retry_delays = [3, 5, 8, 12, 15, 20, 25, 30, 40]
    
    for attempt, delay in enumerate(retry_delays, start=1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            if response.text:
                return response.text
        except Exception as e:
            err_text = str(e)
            
            # Если сервер перегружен (503 / UNAVAILABLE)
            if "503" in err_text or "UNAVAILABLE" in err_text:
                try:
                    # Информируем пользователя о задержке прямо в сообщении
                    bot.edit_message_text(
                        chat_id=status_msg.chat.id,
                        message_id=status_msg.message_id,
                        text=(
                            f"⏳ Серверы Google временно перегружены.\n"
                            f"🔄 Попытка {attempt} из {len(retry_delays)}.\n"
                            f"⏱ Жду {delay} сек. и пробую снова, не переживайте..."
                        )
                    )
                except Exception:
                    pass  # Игнорируем мелкие ошибки Telegram при частых edit_message
                
                time.sleep(delay)
                continue
            
            # Если ошибка другая (например, критический сбой API)
            raise e

    raise RuntimeError("Серверы были недоступны слишком долго. Пожалуйста, отправьте запрос чуть позже.")

@bot.message_handler(content_types=['text'])
def reply(message):
    if not message.text:
        return

    # 1. Сразу уведомляем пользователя, что запрос принят
    status_msg = bot.reply_to(
        message, 
        "⚡ Запрос принят! Формирую ответ..."
    )

    try:
        # Индикатор "печатает..."
        bot.send_chat_action(message.chat.id, 'typing')
        
        # 2. Ждем ответа столько, сколько потребуется
        answer = generate_with_infinite_retry(message.text, status_msg)
        
        # 3. Заменяем статусное сообщение на готовый ответ
        # Если ответ очень длинный (> 4096 символов), Telegram не даст отредактировать целиком
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
            text=f"❌ Произошла ошибка: {e}"
        )

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот успешно запущен!")
    bot.infinity_polling(skip_pending=True)
