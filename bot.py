import os
import time
import base64
import threading
from datetime import datetime
from flask import Flask
import telebot
from telebot import types
from openai import OpenAI

TG_TOKEN = os.environ.get("TG_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

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

PERSONAS = {
    "default": (
        "😇 Обычный",
        "Ты вежливый, четкий и полезный AI-ассистент. Отвечай прямо по делу."
    ),
    "evil": (
        "😈 Злой / Токсик",
        "Ты злой, токсичный, саркастичный собеседник. Считаешь собеседника недалеким, язвительно высмеиваешь вопросы, но ответ сквозь зубы все же даешь."
    ),
    "nerd": (
        "🧐 Душнила",
        "Ты невероятно занудный академик-перфекционист. Душни по каждому поводу, цепляйся к формулировкам и терминам."
    ),
    "bro": (
        "🦝 Свой пацан",
        "Ты четкий пацан с района. Общайся на расслабленном дворовом сленге, просто и с юмором."
    )
}

DEFAULT_PERSONA = "default"

# Пользовательские данные
user_models = {}
user_personas = {}
user_histories = {}
all_users = set()

# Админская статистика и логи
stats = {
    "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "text_requests": 0,
    "photo_requests": 0,
    "errors": 0,
    "max_tokens": 1500
}
recent_logs = []  # Хранит последние 15 событий

def add_log(user_id, action, details=""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] ID:{user_id} -> {action} ({details})"
    recent_logs.append(entry)
    if len(recent_logs) > 15:
        recent_logs.pop(0)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# ================= КЛАВИАТУРЫ =================

def build_model_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key, val in MODELS.items():
        name, _ = val
        btn = types.InlineKeyboardButton(text=name, callback_data="m_" + key)
        kb.add(btn)
    return kb

def build_persona_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key, val in PERSONAS.items():
        title, _ = val
        btn = types.InlineKeyboardButton(text=title, callback_data="p_" + key)
        kb.add(btn)
    return kb

def build_admin_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")
    b2 = types.InlineKeyboardButton(text="📜 Живые логи", callback_data="adm_logs")
    b3 = types.InlineKeyboardButton(text="⚡ Лимит токенов", callback_data="adm_tokens")
    b4 = types.InlineKeyboardButton(text="🧹 Очистить логи", callback_data="adm_clearlogs")
    kb.add(b1, b2)
    kb.add(b3, b4)
    return kb

# ================= АДМИНКА =================

def is_admin(chat_id):
    return ADMIN_ID != 0 and chat_id == ADMIN_ID

@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "⛔ Доступ запрещен. Ты не админ.")
        return

    text = (
        "👑 **Панель Администратора**\n\n"
        f"Всего пользователей: `{len(all_users)}`\n"
        f"Текущий max_tokens: `{stats['max_tokens']}`\n\n"
        "Выбери действие:"
    )
    bot.reply_to(message, text, reply_markup=build_admin_keyboard(), parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    """Рассылка сообщения всем пользователям: /broadcast текст"""
    if not is_admin(message.chat.id):
        return

    msg_text = message.text.replace("/broadcast", "").strip()
    if not msg_text:
        bot.reply_to(message, "Использование: `/broadcast Привет всем от админа!`", parse_mode="Markdown")
        return

    count = 0
    for uid in list(all_users):
        try:
            bot.send_message(uid, f"📢 **Объявление:**\n\n{msg_text}", parse_mode="Markdown")
            count += 1
            time.sleep(0.05)
        except Exception:
            pass

    bot.reply_to(message, f"✅ Сообщение доставлено `{count}` пользователям.")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("adm_"))
def on_admin_click(call):
    if not is_admin(call.message.chat.id):
        bot.answer_callback_query(call.id, "Доступ закрыт!")
        return

    action = call.data

    if action == "adm_stats":
        text = (
            "📊 **Статистика сервера:**\n\n"
            f"🚀 Запуск: `{stats['start_time']}`\n"
            f"👥 Уникальных юзеров: `{len(all_users)}`\n"
            f"💬 Текстовых запросов: `{stats['text_requests']}`\n"
            f"🖼 Обработано фото: `{stats['photo_requests']}`\n"
            f"⚠️ Ошибок шлюза: `{stats['errors']}`\n"
            f"🎯 Лимит токенов: `{stats['max_tokens']}`"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                              reply_markup=build_admin_keyboard(), parse_mode="Markdown")

    elif action == "adm_logs":
        if not recent_logs:
            log_text = "Логи пока пусты."
        else:
            log_text = "\n".join(recent_logs[-10:])
        text = f"📜 **Последние 10 логов:**\n\n```text\n{log_text}\n```"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                              reply_markup=build_admin_keyboard(), parse_mode="Markdown")

    elif action == "adm_tokens":
        kb = types.InlineKeyboardMarkup(row_width=3)
        kb.add(
            types.InlineKeyboardButton("500", callback_data="tok_500"),
            types.InlineKeyboardButton("1500", callback_data="tok_1500"),
            types.InlineKeyboardButton("3000", callback_data="tok_3000")
        )
        kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="adm_stats"))
        bot.edit_message_text("⚡ Выбери новый лимит `max_tokens`:", 
                              call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    elif action == "adm_clearlogs":
        recent_logs.clear()
        bot.answer_callback_query(call.id, "Логи очищены!")
        bot.edit_message_text("🧹 Логи очищены.", call.message.chat.id, call.message.message_id, 
                              reply_markup=build_admin_keyboard())

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("tok_"))
def on_token_change(call):
    if not is_admin(call.message.chat.id):
        return
    val = int(call.data.replace("tok_", ""))
    stats["max_tokens"] = val
    bot.answer_callback_query(call.id, f"max_tokens установлен на {val}")
    cmd_admin(call.message)

# ================= ОБЫЧНЫЕ КОМАНДЫ =================

@bot.message_handler(commands=['model', 'models'])
def cmd_model(message):
    all_users.add(message.chat.id)
    uid = message.chat.id
    current = user_models.get(uid, DEFAULT_MODEL)
    text = "🤖 Текущая модель:\n" + current + "\n\nВыберите модель:"
    bot.reply_to(message, text, reply_markup=build_model_keyboard())

@bot.message_handler(commands=['mode', 'persona', 'mood'])
def cmd_persona(message):
    all_users.add(message.chat.id)
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
        add_log(call.message.chat.id, "Сменил модель", slug)
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
        add_log(call.message.chat.id, "Сменил настроение", name)
        bot.answer_callback_query(call.id, "Характер: " + name)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🎭 Установлено настроение:\n" + name
        )

@bot.message_handler(commands=['clear', 'reset', 'start'])
def cmd_reset(message):
    all_users.add(message.chat.id)
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

# ================= ОБРАБОТКА НЕЙРОСЕТИ =================

def send_to_ai(uid, user_content_payload, status_msg):
    model = user_models.get(uid, DEFAULT_MODEL)
    p_key = user_personas.get(uid, DEFAULT_PERSONA)
    system_prompt = PERSONAS[p_key][1]

    if uid not in user_histories:
        user_histories[uid] = []

    user_histories[uid].append({"role": "user", "content": user_content_payload})

    if len(user_histories[uid]) > 10:
        user_histories[uid] = user_histories[uid][-10:]

    full_messages = [{"role": "system", "content": system_prompt}] + user_histories[uid]

    try:
        bot.send_chat_action(uid, 'typing')

        resp = ai_client.chat.completions.create(
            model=model,
            messages=full_messages,
            max_tokens=stats["max_tokens"]
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
        stats["errors"] += 1
        add_log(uid, "ОШИБКА", str(e)[:30])
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text="❌ Ошибка: " + str(e)
        )

@bot.message_handler(content_types=['photo'])
def on_photo(message):
    all_users.add(message.chat.id)
    stats["photo_requests"] += 1
    uid = message.chat.id
    caption = message.caption or "Что изображено на этой картинке?"
    model = user_models.get(uid, DEFAULT_MODEL)

    add_log(uid, "Отправил фото", model)
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
        stats["errors"] += 1
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text="❌ Ошибка при загрузке фото: " + str(e)
        )

@bot.message_handler(content_types=['text'])
def on_text(message):
    all_users.add(message.chat.id)
    stats["text_requests"] += 1
    uid = message.chat.id
    model = user_models.get(uid, DEFAULT_MODEL)
    add_log(uid, "Текст", message.text[:20])

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
