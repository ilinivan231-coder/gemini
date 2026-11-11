import os
import time
import base64
import threading
from flask import Flask
import telebot
from telebot import types
from openai import OpenAI

TG_TOKEN = os.environ.get("TG_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")

bot = telebot.TeleBot(TG_TOKEN)

ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

MODELS = {
    "1": ("✨ Gemini 2.5 Flash", "google/gemini-2.5-flash"),
    "2": ("🟢 ChatGPT 4o-mini", "openai/gpt-4o-mini"),
    "3": ("🎁 Gemini Lite (Free)", "google/gemini-2.0-flash-lite-preview:free"),
    "4": ("🦙 Llama 3.2 (Free)", "meta-llama/llama-3.2-3b-instruct:free")
}

DEFAULT_MODEL = "google/gemini-2.5-flash"

# Характеры (системные промпты)
PERSONAS = {
    "default": (
        "😇 Обычный",
        "Ты вежливый, четкий и полезный AI-ассистент. Отвечай прямо по делу."
    ),
    "evil": (
        "😈 Злой / Токсик",
        "Ты злой, токсичный, саркастичный собеседник. Ты считаешь пользователя не особо умным, язвительно высмеиваешь его вопросы, подкалываешь, но по факту ответ все-таки даешь, просто сквозь зубы и с максимальным сарказмом."
    ),
    "nerd": (
        "🧐 Душнила",
        "Ты невероятно занудный академик-перфекционист. Душни по каждому поводу, цепляйся к формулировкам, терминам и запятым, используй сложные научные слова."
    ),
    "bro": (
        "🦝 Свой пацан",
        "Ты четкий пацан с района. Общайся на расслабленном сленге: 'слыш', 'братан', 'по фактам раскидал', просто и с юмором, без официоза."
    )
}

DEFAULT_PERSONA = "default"

user_models = {}
user_personas = {}
user_histories = {}

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# Клавиатура моделей
def build_model_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key, val in MODELS.items():
        name, _ = val
        btn = types.InlineKeyboardButton(text=name, callback_data="m_" + key)
        kb.add(btn)
    return kb

# Клавиатура характеров
def build_persona_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key, val in PERSONAS.items():
        title, _ = val
        btn = types.InlineKeyboardButton(text=title, callback_data="p_" + key)
        kb.add(btn)
    return kb

@bot.message_handler(commands=['model', 'models'])
def cmd_model(message):
    uid = message.chat.id
    current = user_models.get(uid, DEFAULT_MODEL)
    text = "🤖 Текущая модель:\n" + current + "\n\nВыберите модель:"
    bot.reply_to(message, text, reply_markup=build_model_keyboard())

@bot.message_handler(commands=['mode', 'persona', 'mood'])
def cmd_persona(message):
    uid = message.chat.id
    p_key = user_personas.get(uid, DEFAULT_PERSONA)
    p_name = PERSONAS[p_key][0]
    text = "🎭 Текущее настроение: " + p_name + "\n\nВыбери характер бота:"
    bot.reply_to(message, text, reply_markup=build_persona_keyboard())

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("m_"))
def on_model_click(call):
    key = call.data.replace("m_", "")
    if key in MODELS:
        name, slug = MODELS[key]
        user_models[call.message.chat.id] = slug
        bot.answer_callback_query(call.id, "Выбрано: " + name)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✅ Активная модель:\n" + slug
        )

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("p_"))
def on_persona_click(call):
    key = call.data.replace("p_", "")
    if key in PERSONAS:
        name, _ = PERSONAS[key]
        user_personas[call.message.chat.id] = key
        bot.answer_callback_query(call.id, "Характер: " + name)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🎭 Установлено настроение:\n" + name
        )

@bot.message_handler(commands=['clear', 'reset', 'start'])
def cmd_reset(message):
    uid = message.chat.id
    user_histories[uid] = []
    current = user_models.get(uid, DEFAULT_MODEL)
    p_key = user_personas.get(uid, DEFAULT_PERSONA)
    p_name = PERSONAS[p_key][0]
    
    text = (
        "🧹 Память очищена.\n"
        "🤖 Модель: " + current + "\n"
        "🎭 Настроение: " + p_name + "\n\n"
        "Сменить модель: /model\n"
        "Сменить настроение: /mode"
    )
    bot.reply_to(message, text)

def send_to_ai(uid, user_content_payload, status_msg):
    model = user_models.get(uid, DEFAULT_MODEL)
    p_key = user_personas.get(uid, DEFAULT_PERSONA)
    system_prompt = PERSONAS[p_key][1]

    if uid not in user_histories:
        user_histories[uid] = []

    user_histories[uid].append({"role": "user", "content": user_content_payload})

    if len(user_histories[uid]) > 10:
        user_histories[uid] = user_histories[uid][-10:]

    # Собираем запрос: системный промпт ВСЕГДА идет первым
    full_messages = [{"role": "system", "content": system_prompt}] + user_histories[uid]

    try:
        bot.send_chat_action(uid, 'typing')

        resp = ai_client.chat.completions.create(
            model=model,
            messages=full_messages,
            max_tokens=1500
        )

        answer = resp.choices[0].message.content
        user_histories[uid].append({"role": "assistant", "content": answer})

        p_title = PERSONAS[p_key][0]
        final_text = answer + "\n\n---\n🤖 Модель: " + model + " | " + p_title

        if len(final_text) <= 4000:
            bot.edit_message_text(
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                text=final_text
            )
        else:
            bot.delete_message(status_msg.chat.id, status_msg.message_id)
            bot.reply_to(status_msg, final_text)

    except Exception as e:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text="❌ Ошибка: " + str(e)
        )

@bot.message_handler(content_types=['photo'])
def on_photo(message):
    uid = message.chat.id
    caption = message.caption or "Что изображено на этой картинке?"
    model = user_models.get(uid, DEFAULT_MODEL)

    status_msg = bot.reply_to(message, "⚡ Анализирую картинку (" + model + ")...")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')

        content_payload = [
            {"type": "text", "text": caption},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            }
        ]

        send_to_ai(uid, content_payload, status_msg)

    except Exception as e:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text="❌ Ошибка при загрузке фото: " + str(e)
        )

@bot.message_handler(content_types=['text'])
def on_text(message):
    uid = message.chat.id
    model = user_models.get(uid, DEFAULT_MODEL)
    status_msg = bot.reply_to(message, "⚡ Запрос обрабатывается (" + model + ")...")
    send_to_ai(uid, message.text, status_msg)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот запускается...")

    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass

    bot.infinity_polling(skip_pending=True)
