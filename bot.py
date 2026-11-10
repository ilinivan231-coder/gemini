import os
import time
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

AVAILABLE_MODELS = {
    "gemini_flash": {
        "name": "✨ Gemini 2.5 Flash",
        "slug": "google/gemini-2.5-flash"
    },
    "gpt_4o_mini": {
        "name": "🟢 ChatGPT (GPT-4o mini)",
        "slug": "openai/gpt-4o-mini"
    },
    "gemini_free": {
        "name": "🎁 Gemini Lite (Free)",
        "slug": "google/gemini-2.0-flash-lite-preview:free"
    },
    "llama_free": {
        "name": "🦙 Llama 3.2 3B (Free)",
        "slug": "meta-llama/llama-3.2-3b-instruct:free"
    }
}

DEFAULT_MODEL_KEY = "gemini_flash"

user_models = {}
user_histories = {}

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running with model switcher!"

def make_model_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for key, data in AVAILABLE_MODELS.items():
        button = types.InlineKeyboardButton(text=data["name"], callback_data=f"set_model:{key}")
        keyboard.add(button)
    return keyboard

@bot.message_handler(commands=['model', 'models'])
def choose_model(message):
    current_slug = user_models.get(message.chat.id, AVAILABLE_MODELS[DEFAULT_MODEL_KEY]["slug"])
    bot.reply_to(
        message,
        f"🤖 *Текущая модель:* `{current_slug}`\n\nВыберите модель из списка:",
        reply_markup=make_model_keyboard(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_model:"))
def handle_model_selection(call):
    model_key = call.data.split(":")[1]
    if model_key in AVAILABLE_MODELS:
        selected = AVAILABLE_MODELS[model_key]
        user_models[call.message.chat.id] = selected["slug"]
        bot.answer_callback_query(call.id, f"Выбрана модель: {selected['name']}")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ *Модель изменена!*\n\nТекущая: `{selected['slug']}`",
            parse_mode="Markdown"
        )
    else:
        bot.answer_callback_query(call.id, "Неизвестная модель.")

@bot.message_handler(commands=['clear', 'reset', 'start'])
def reset_memory(message):
    user_id = message.chat.id
    user_histories[user_id] =
