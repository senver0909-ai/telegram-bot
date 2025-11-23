import os
import asyncio
import random
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage

# ================= НАСТРОЙКИ =================
TOKEN = os.getenv("BOT_TOKEN")  # <- токен ставим в переменные окружения на Render
DB_PATH = "bot_data.db"

# ================= БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            ttt_wins INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            coupon TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id, username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
    conn.close()

def add_ttt_win(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET ttt_wins = ttt_wins + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    c.execute("SELECT ttt_wins FROM users WHERE user_id = ?", (user_id,))
    wins = c.fetchone()[0]
    conn.close()
    return wins

def reset_ttt_wins(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET ttt_wins = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_coupon(user_id, coupon):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO coupons (user_id, coupon) VALUES (?, ?)", (user_id, coupon))
    conn.commit()
    conn.close()

def get_coupons(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT coupon, created_at FROM coupons WHERE user_id = ?", (user_id,))
    coupons = c.fetchall()
    conn.close()
    return coupons

# ================= КУПОНЫ =================
def get_random_coupon():
    coupons = [
        "🎟 10% скидка в KFC 🍗",
        "🎟 15% скидка в Starbucks ☕",
        "🎟 20% скидка в Nike 👟",
        "🎟 Бесплатный десерт в McDonald's 🍰",
        "🎟 5% скидка в Burger King 🍔",
    ]
    return random.choice(coupons)

# ================= ИГРА: КРЕСТИКИ-НОЛИКИ =================
class TicTacToe:
    def __init__(self):
        self.board = [[" "]*3 for _ in range(3)]

    def render_board(self):
        return "\n".join([" | ".join(row) for row in self.board])

    def get_keyboard(self):
        kb = InlineKeyboardMarkup(row_width=3)
        for i in range(3):
            row = []
            for j in range(3):
                text = self.board[i][j] if self.board[i][j] != " " else "⬜"
                row.append(InlineKeyboardButton(text=text, callback_data=f"ttt_{i}_{j}"))
            kb.add(*row)
        return kb

    def make_move(self, x, y):
        if self.board[x][y] != " ":
            return "continue"
        self.board[x][y] = "X"
        if self.check_win("X"):
            return "win"
        if all(cell != " " for row in self.board for cell in row):
            return "draw"
        self.bot_move()
        if self.check_win("O"):
            return "lose"
        if all(cell != " " for row in self.board for cell in row):
            return "draw"
        return "continue"

    def bot_move(self):
        empty = [(i, j) for i in range(3) for j in range(3) if self.board[i][j] == " "]
        if empty:
            x, y = random.choice(empty)
            self.board[x][y] = "O"

    def check_win(self, sym):
        for i in range(3):
            if all(self.board[i][j] == sym for j in range(3)) or all(self.board[j][i] == sym for j in range(3)):
                return True
        if all(self.board[i][i] == sym for i in range(3)) or all(self.board[i][2 - i] == sym for i in range(3)):
            return True
        return False

# ================= ИГРА: САПЁР =================
class Minesweeper:
    def __init__(self, size=5, mines=5):
        self.size = size
        self.mines = mines
        self.board = [["⬜"]*size for _ in range(size)]
        self.mine_coords = set()
        while len(self.mine_coords) < mines:
            self.mine_coords.add((random.randint(0, size-1), random.randint(0, size-1)))
        self.opened = set()

    def render_board(self):
        return "\n".join([" ".join(row) for row in self.board])

    def get_keyboard(self):
        kb = InlineKeyboardMarkup(row_width=self.size)
        for i in range(self.size):
            row = []
            for j in range(self.size):
                row.append(InlineKeyboardButton(text=self.board[i][j], callback_data=f"mine_{i}_{j}"))
            kb.add(*row)
        return kb

    def open_cell(self, x, y):
        if (x, y) in self.opened:
            return "continue"
        self.opened.add((x, y))
        if (x, y) in self.mine_coords:
            self.board[x][y] = "💣"
            return "lose"
        mines_near = self.count_near(x, y)
        self.board[x][y] = str(mines_near)
        if len(self.opened) == self.size*self.size - self.mines:
            return "win"
        return "continue"

    def count_near(self, x, y):
        count = 0
        for dx in [-1,0,1]:
            for dy in [-1,0,1]:
                if dx==0 and dy==0:
                    continue
                nx, ny = x+dx, y+dy
                if 0<=nx<self.size and 0<=ny<self.size and (nx,ny) in self.mine_coords:
                    count += 1
        return count

# ================= ЛОГИКА БОТА =================
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
user_games = {}

def main_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🎮 Крестики-нолики", callback_data="game_ttt"),
        InlineKeyboardButton("💣 Сапёр", callback_data="game_mines"),
        InlineKeyboardButton("🎟 Мои купоны", callback_data="my_coupons"),
    )
    return kb

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    get_user(message.from_user.id, message.from_user.username)
    await message.answer("👋 Привет! Выбери игру:", reply_markup=main_menu())

# Крестики
@dp.callback_query(F.data == "game_ttt")
async def start_ttt(callback: types.CallbackQuery):
    await callback.answer()
    game = TicTacToe()
    user_games[callback.from_user.id] = game
    await callback.message.answer("🎮 Игра 'Крестики-нолики' начата")
    await callback.message.answer(game.render_board(), reply_markup=game.get_keyboard())

@dp.callback_query(F.data.startswith("ttt_"))
async def handle_ttt(callback: types.CallbackQuery):
    await callback.answer()
    game = user_games.get(callback.from_user.id)
    if not game:
        await callback.message.answer("Начни игру командой /start")
        return
    _, x, y = callback.data.split("_")
    result = game.make_move(int(x), int(y))
    if result == "continue":
        await callback.message.edit_text(game.render_board(), reply_markup=game.get_keyboard())
    elif result == "win":
        wins = add_ttt_win(callback.from_user.id)
        if wins >= 5:
            coupon = get_random_coupon()
            add_coupon(callback.from_user.id, coupon)
            reset_ttt_wins(callback.from_user.id)
            await callback.message.answer(f"🎉 Купон: {coupon}")
        else:
            await callback.message.answer(f"✅ Побед подряд: {wins}/5")
        await callback.message.answer("Хотите снова?", reply_markup=main_menu())
    elif result == "lose":
        await callback.message.answer("❌ Проигрыш.", reply_markup=main_menu())
    elif result == "draw":
        await callback.message.answer("🤝 Ничья.", reply_markup=main_menu())

# Сапёр
@dp.callback_query(F.data == "game_mines")
async def start_mines(callback: types.CallbackQuery):
    await callback.answer()
    game = Minesweeper()
    user_games[callback.from_user.id] = game
    await callback.message.answer("💣 Сапёр начат")
    await callback.message.answer(game.render_board(), reply_markup=game.get_keyboard())

@dp.callback_query(F.data.startswith("mine_"))
async def handle_mines(callback: types.CallbackQuery):
    await callback.answer()
    game = user_games.get(callback.from_user.id)
    if not game:
        await callback.message.answer("Начни игру командой /start")
        return
    _, x, y = callback.data.split("_")
    result = game.open_cell(int(x), int(y))
    if result == "continue":
        await callback.message.edit_text(game.render_board(), reply_markup=game.get_keyboard())
    elif result == "lose":
        await callback.message.answer("💥 Бомба! Проигрыш.", reply_markup=main_menu())
    elif result == "win":
        coupon = get_random_coupon()
        add_coupon(callback.from_user.id, coupon)
        await callback.message.answer(f"🎉 Купон: {coupon}", reply_markup=main_menu())

# Купоны
@dp.callback_query(F.data == "my_coupons")
async def show_coupons(callback: types.CallbackQuery):
    await callback.answer()
    coupons = get_coupons(callback.from_user.id)
    if not coupons:
        await callback.message.answer("😢 Нет купонов.", reply_markup=main_menu())
    else:
        text = "🎟 Ваши купоны:\n"
        for cpn, date in coupons:
            text += f"• {cpn} (получен {date})\n"
        await callback.message.answer(text, reply_markup=main_menu())

# Запуск
async def main():
    init_db()
    print("🚀 Бот стартует...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
