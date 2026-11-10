import os
import time
import threading
from flask import Flask
import telebot
from openai import OpenAI

TG_TOKEN = os.environ.get("TG_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")

bot = telebot.TeleBot(TG_TOKEN)

ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running via OpenRouter!"

def get_working_free_models():
    """Автоматически получает список доступных в эту секунду бесплатных моделей"""
    try:
        models_data = ai_client.models.list()
        # Ищем все модели, у которых в названии есть ':free'
        free_models = [m.id for m in models_data.data if m.id.endswith(':free')]
        if free_models:
            return free_models
    except Exception as e:
        print(f"Не удалось получить список моделей: {e}")
    
    # Запасной список, если запрос к списку упадет
    return ["meta-llama/llama-3.2-3b-instruct:free", "google/gemini-2.0-flash-lite-preview:free"]

def get_ai_response(text):
    """Опрашивает реально работающие в данный момент бесплатные модели"""
    available_models = get_working_free_models()
    last_error = None

    for model_name in available_models:
        try:
            print(f"Пробуем отправить запрос в модель: {model_name}")
            completion = ai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": text}
                ]
            )
            if completion.choices and completion.choices[0].message.content:
                return completion.choices[0].message.content
        except Exception as e:
            last_error = e
            print(f"Сбой с моделью {model_name}: {e}")
            continue

    raise last_error

@bot.message_handler(content_types=['text'])
def reply(message):
    if not message.text:
        return

    status_msg = bot.reply_to(message, "⚡ Запрос принят! Подбираю рабочую модель...")

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        answer = get_ai_response(message.text)

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
            text=f"❌ Ошибка шлюза: {e}"
        )

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот запускается...")
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception as e:
        print(f"Ошибка при сбросе вебхука: {e}")

    bot.infinity_polling(skip_pending=True)
