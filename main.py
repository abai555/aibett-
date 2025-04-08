import telebot
from flask import Flask
from threading import Thread
from groq import Groq
import stripe
import requests
import time
import sqlite3

# === API KEYS ===
TELEGRAM_TOKEN = "7710632976:AAEf3KbdDQ8lV6LAR8A2iRKGNcIFbrUQa8A"
GROQ_API_KEY = "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"
STRIPE_SECRET_KEY = "sk_test_51R4QVlP3En7UClAYUZecvKYKgWiUNC9V2zYnIpfl5aTOJc84Qe9VGUUOMRW04KgAw7VyM9JY9uXhHTALKSows5EB00yNqVAerJ"
NOWPAYMENTS_API_KEY = "OeYN3CN4C88rU8RVAW94yw+M8hEZ+mep"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
stripe.api_key = STRIPE_SECRET_KEY
client = Groq(api_key=GROQ_API_KEY)

# === Flask для UptimeRobot ===
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"
def run():
    app.run(host='0.0.0.0', port=8080)
def keep_alive():
    Thread(target=run).start()
keep_alive()

# === SQLite база ===
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    subscription TEXT,
    expiry_date INTEGER
)
""")
conn.commit()

# === Команда /start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Analyze Match")
    bot.send_message(
        message.chat.id,
        "🤖 <b>AI Match Analyzer</b> — an AI-powered match analysis bot.\n\n"
        "🔹 <b>Features:</b>\n"
        "- AI-based match analysis\n"
        "- Payments via Stripe & Crypto\n"
        "- Subscription plans\n\n"
        "👇 Press the button to start analyzing!",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Кнопка "Анализ матча" ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def ask_for_match(message):
    user_id = message.chat.id
    cursor.execute("SELECT expiry_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row and row[0] > int(time.time()):
        bot.send_message(user_id, "✅ Send match details to analyze:")
    else:
        show_subscriptions(user_id)

# === Подписки ===
def show_subscriptions(user_id):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("💳 Pay $7 (Stripe)", callback_data="pay_7"))
    markup.add(telebot.types.InlineKeyboardButton("💳 Pay $30 (Stripe)", callback_data="pay_30"))
    markup.add(telebot.types.InlineKeyboardButton("💳 Pay $250 (Stripe)", callback_data="pay_250"))
    markup.add(telebot.types.InlineKeyboardButton("🪙 Pay with Crypto (NOWPayments)", callback_data="crypto_pay"))

    bot.send_message(
        user_id,
        "💰 <b>Choose your subscription:</b>\n"
        "🔹 One-time analysis – $7\n"
        "🔹 Weekly – $30\n"
        "🔹 Yearly – $250\n\n"
        "💳 Pay via Stripe or Crypto (NOWPayments).",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Stripe оплатa ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def handle_stripe(call):
    user_id = call.message.chat.id
    amount = int(call.data.split("_")[1])
    duration = 86400 if amount == 7 else 7 * 86400 if amount == 30 else 365 * 86400

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "AI Match Analysis Subscription"},
                "unit_amount": amount * 100,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"https://t.me/YOUR_BOT_USERNAME?start=success_{user_id}_{duration}",
        cancel_url="https://t.me/YOUR_BOT_USERNAME",
    )
    bot.send_message(user_id, f"💳 Complete your payment: [Click here]({session.url})", parse_mode="Markdown")

# === Крипто-оплата ===
@bot.callback_query_handler(func=lambda call: call.data == "crypto_pay")
def handle_crypto(call):
    user_id = call.message.chat.id
    payment_data = {
        "price_amount": 30,
        "price_currency": "usd",
        "pay_currency": "btc",
"order_id": str(user_id),
        "ipn_callback_url": "https://yourdomain.com/ipn"
    }
    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
        "Content-Type": "application/json"
    }
    res = requests.post("https://api.nowpayments.io/v1/payment", json=payment_data, headers=headers)
    if res.status_code == 200:
        url = res.json()["invoice_url"]
        bot.send_message(user_id, f"🪙 Complete your payment: [Click here]({url})", parse_mode="Markdown")
    else:
        bot.send_message(user_id, "❌ Crypto payment failed. Try again later.")

# === Обработка успешной оплаты через Stripe ===
@bot.message_handler(commands=['success'])
def success(message):
    try:
        parts = message.text.split("_")
        user_id = int(parts[1])
        duration = int(parts[2])
        expiry = int(time.time()) + duration
        cursor.execute("INSERT OR REPLACE INTO users (user_id, subscription, expiry_date) VALUES (?, ?, ?)",
                       (user_id, "active", expiry))
        conn.commit()
        bot.send_message(user_id, "✅ Subscription activated! Send match details.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error confirming payment: {e}")

# === Анализ матча через Groq ===
@bot.message_handler(func=lambda msg: True)
def analyze_match(msg):
    user_id = msg.chat.id
    cursor.execute("SELECT expiry_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row and row[0] > int(time.time()):
        bot.send_message(user_id, "⚡ Analyzing the match...")
        try:
            prompt = f"Give a concise match analysis and approximate odds:\n\n{msg.text}"
            response = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.choices[0].message.content
            for i in range(0, len(text), 4000):
                bot.send_message(user_id, text[i:i+4000])
        except Exception as e:
            bot.send_message(user_id, f"❌ Error: {e}")
    else:
        show_subscriptions(user_id)

# === Запуск бота ===
bot.polling()
