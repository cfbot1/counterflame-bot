
import telebot
import sqlite3
from telebot import types
from datetime import datetime

# --- НАСТРОЙКИ ---
API_TOKEN = 'ТВОЙ_ТОКЕН'
ADMIN_ID = 123456789 # Твой ID

bot = telebot.TeleBot(API_TOKEN)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('esports_pro.db', check_same_thread=False)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS players 
        (user_id INTEGER PRIMARY KEY, player_id TEXT UNIQUE, nick TEXT UNIQUE, 
        photo_id TEXT, title TEXT, clan TEXT, elo INTEGER DEFAULT 1000, 
        matches INTEGER DEFAULT 0, join_date TEXT, reg_count INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS reviews 
        (from_id INTEGER, to_pid TEXT, rating INTEGER, comment TEXT)''')
    conn.commit()
    return conn

db = init_db()

# --- КНОПКИ ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Поиск", "👤 Мой профиль")
    markup.row("📜 Список игроков", "🛡 Клан")
    markup.row("⚔️ Match Check")
    return markup

# --- ФУНКЦИИ ХЕЛПЕРЫ ---
def get_days_in_bot(date_str):
    join_date = datetime.strptime(date_str, '%Y-%m-%d')
    delta = datetime.now() - join_date
    return delta.days

def show_profile(chat_id, identifier):
    cur = db.cursor()
    cur.execute("SELECT * FROM players WHERE player_id=? OR nick=?", (identifier, identifier))
    p = cur.fetchone()
    if not p: return bot.send_message(chat_id, "👤 Игрок не найден.")

    days = get_days_in_bot(p[8])
    cur.execute("SELECT rating, comment FROM reviews WHERE to_pid=?", (p[1],))
    revs = cur.fetchall()
    rev_text = "\n".join([f"⭐️ {r[0]} | {r[1]}" for r in revs]) or "Нет отзывов."

    cap = (f"🆔 ID: {p[1]}\n👤 Ник: {p[2]}\n🏆 Титул: {p[4] or '-'}\n🛡 Клан: {p[5] or '-'}\n\n"
           f"📈 Эло: {p[6]}\n🎮 Матчей: {p[7]}\n📅 Дней в боте: {days}\n\n💸 Отзывы:\n{rev_text}")
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Оценить ⭐", callback_data=f"rate_{p[1]}"))
    kb.add(types.InlineKeyboardButton("Пригласить в клан 🛡", callback_data=f"inv_{p[1]}"))
    bot.send_photo(chat_id, p[3], caption=cap, reply_markup=kb)

# --- ОБРАБОТКА КОМАНД ---
@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "🔥 Counterflame System", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "👤 Мой профиль")
def my_p(m):
    cur = db.cursor()
    cur.execute("SELECT player_id FROM players WHERE user_id=?", (m.from_user.id,))
    res = cur.fetchone()
    if res: show_profile(m.chat.id, res[0])
    else: bot.send_message(m.chat.id, "Зарегистрируйтесь: /register")

@bot.message_handler(func=lambda m: m.text == "🔍 Поиск")
def search(m):
    msg = bot.send_message(m.chat.id, "Введите ID или Ник:")
    bot.register_next_step_handler(msg, lambda msg: show_profile(msg.chat.id, msg.text))

@bot.message_handler(func=lambda m: m.text == "📜 Список игроков")
def list_p(m):
    cur = db.cursor()
    cur.execute("SELECT player_id, nick FROM players")
    rows = cur.fetchall()
    if not rows: return bot.send_message(m.chat.id, "Список пуст.")
    text = "📜 Список:\n"
    for r in rows:
        text += f"• {r[0]} (ID: {r[1]}) /view_{r[0]}\n"
    bot.send_message(m.chat.id, text)

@bot.message_handler(func=lambda m: m.text.startswith('/view_'))
def view_cmd(m):
    pid = m.text.replace('/view_', '')
    show_profile(m.chat.id, pid)

# --- РЕГИСТРАЦИЯ ---
@bot.message_handler(commands=['register'])
def reg(m):
    cur = db.cursor()
    cur.execute("SELECT reg_count FROM players WHERE user_id=?", (m.from_user.id,))
    res = cur.fetchone()
    if res and res[0] >= 4: return bot.send_message(m.chat.id, "❌ Лимит изменений исчерпан.")
    msg = bot.send_message(m.chat.id, "Пришли ФОТО + в подписи 'ID НИК'")
    bot.register_next_step_handler(msg, proc_reg)

def proc_reg(m):
    if not m.photo: return bot.send_message(m.chat.id, "Нужно фото!")
    try:
        data = m.caption.split()
        p_id, nick = data[0], data[1]
        date_now = datetime.now().strftime('%Y-%m-%d')
        cur = db.cursor()
        cur.execute("""INSERT INTO players (user_id, player_id, nick, photo_id, join_date, reg_count) 
            VALUES (?,?,?,?,?,1) ON CONFLICT(user_id) DO UPDATE SET 
            player_id=excluded.player_id, nick=excluded.nick, photo_id=excluded.photo_id, 
            reg_count=reg_count+1""", (m.from_user.id, p_id, nick, m.photo[-1].file_id, date_now))
        db.commit()
        bot.send_message(m.chat.id, "✅ Профиль создан!")
    except: bot.send_message(m.chat.id, "❌ Ошибка! ID или Ник уже заняты.")

# --- MATCH CHECK ---
@bot.message_handler(func=lambda m: m.text == "⚔️ Match Check")
def match_c(m):
    msg = bot.send_message(m.chat.id, "Пришли скриншот матча:")
    bot.register_next_step_handler(msg, proc_match)

def proc_match(m):
    if not m.photo: return bot.send_message(m.chat.id, "Нужно фото!")
    kb = types.InlineKeyboardMarkup()
    vals = ["+35", "+50", "+65", "-5", "+5", "+0", "-25"]
    btns = [types.InlineKeyboardButton(v, callback_data=f"elo_{m.from_user.id}_{v}") for v in vals]
    kb.add(*btns)
    bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=f"Результат от @{m.from_user.username}", reply_markup=kb)
    bot.send_message(m.chat.id, "⏳ Скриншот отправлен админу на проверку.")

# --- CALLBACKS (Эло, Кланы, Отзывы) ---
@bot.callback_query_handler(func=lambda call: True)
def calls(call):
    # Эло (Админ)
    if call.data.startswith("elo_"):
        _, uid, val = call.data.split("_")
        cur = db.cursor()
        cur.execute("UPDATE players SET elo=elo+?, matches=matches+1 WHERE user_id=?", (int(val), uid))
        db.commit()
        bot.send_message(uid, f"📊 Твой результат проверен: {val} Эло!")
        bot.edit_message_caption(f"Проверено: {val}", call.message.chat.id, call.message.message_id)

    # Кланы (Набор и приглашение) - логика как в прошлом коде
    # ... (код для acc_, dec_, inv_, apply_ из предыдущего сообщения) ...

# --- АДМИНКА ---
@bot.message_handler(commands=['del_profile'])
def del_p(m):
    if m.from_user.id == ADMIN_ID:
        pid = m.text.split()[1]
        cur = db.cursor(); cur.execute("DELETE FROM players WHERE player_id=?", (pid,)); db.commit()
        bot.send_message(m.chat.id, f"Удален {pid}")

@bot.message_handler(commands=['set_title'])
def set_t(m):
    if m.from_user.id == ADMIN_ID:
        _, pid, title = m.text.split(maxsplit=2)
        cur = db.cursor(); cur.execute("UPDATE players SET title=? WHERE player_id=?", (title, pid)); db.commit()
        bot.send_message(m.chat.id, "Титул выдан.")

bot.polling(none_stop=True)
