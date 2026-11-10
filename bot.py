import os
import threading
from flask import Flask
import telebot
from openai import OpenAI

# Получаем токены из настроек Render
TG_TOKEN = os.environ.get("TG_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")

bot = telebot.TeleBot(TG_TOKEN)

# Подключение к OpenRouter через клиент OpenAI
ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

# Бесплатная быстрая модель Gemini без лимита в 20 сообщений
MODEL_NAME = "google/gemini-2.0-flash-exp:free"

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running via OpenRouter!"

@bot.message_handler(content_types=['text'])
def reply(message):
    if not message.text:
        return

    # Сообщение о статусе
    status_msg = bot.reply_to(message, "⚡ Запрос принят! Формирую ответ...")

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        completion = ai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "user", "content": message.text}
            ]
        )
        
        answer = completion.choices[0].message.content

        # Отправляем ответ обратно
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
            text=f"❌ Ошибка: {e}"
        )

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот успешно запущен!")
    bot.infinity_polling(skip_pending=True)
