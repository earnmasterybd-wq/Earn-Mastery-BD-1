import asyncio
import logging
import random
import string
import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
import aiofiles
import pytz

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MONGO_URI = os.getenv("MONGO_URI", "")
DATABASE_NAME = "earning_bot"

# Payment Methods
PAYMENT_METHODS = [
    {"id": "bkash", "name": "bKash", "active": True},
    {"id": "nagad", "name": "Nagad", "active": True},
    {"id": "rocket", "name": "Rocket", "active": True},
    {"id": "usdt", "name": "USDT (TRC20)", "active": True},
    {"id": "cryptobot", "name": "CryptoBot", "active": True},
    {"id": "xrocket", "name": "xRocket", "active": True}
]

# System Settings
MIN_WITHDRAW = 100
MAX_WITHDRAW = 50000
REFERRAL_BONUS = 50
WHEEL_SPIN_REWARDS = [10, 20, 50, 100, 200, 500, 1000]

# Language texts
TEXTS = {
    "en": {
        "welcome": "👋 Welcome to EarnBot!\n\nEarn money by completing tasks, referring friends, and spinning the wheel!",
        "profile": "👤 *Profile*\n\nUser ID: `{user_id}`\nUsername: @{username}\nBalance: 💰 {balance} Taka\nTotal Earned: 📈 {total_earned} Taka\nTotal Withdrawn: 💸 {total_withdrawn} Taka\nReferrals: 👥 {referrals}\nLanguage: {language}",
        "tasks": "📋 *Available Tasks*\n\nComplete tasks to earn rewards!",
        "no_tasks": "❌ No tasks available at the moment.",
        "task_details": "📌 *{title}*\n\n{description}\n\n💰 Reward: {reward} Taka",
        "task_completed": "✅ Task completed successfully!\n\nYou earned: {reward} Taka",
        "task_already_completed": "❌ You have already completed this task!",
        "deposit": "💳 *Deposit Money*\n\nSelect your payment method:",
        "deposit_instruction": "💰 *Deposit Request*\n\nMethod: {method}\nAmount: {amount} Taka\n\nPlease send {amount} Taka to:\n{payment_info}\n\nAfter sending, click 'I've Sent' to submit your transaction details.",
        "deposit_submit": "📝 *Submit Transaction Details*\n\nPlease send:\n1️⃣ Transaction ID\n2️⃣ Amount (if different)\n3️⃣ Screenshot (optional)\n\nFormat:\n`TXNID123456 | 500`\nOr just the transaction ID and we'll use the amount you selected.",
        "deposit_request_sent": "✅ Deposit request submitted!\n\nTransaction ID: {txn_id}\nAmount: {amount} Taka\n\nAdmin will verify and approve soon.",
        "withdraw": "💸 *Withdraw Money*\n\nCurrent Balance: {balance} Taka\nMin: {min_amount} Taka\nMax: {max_amount} Taka\n\nSelect withdrawal method:",
        "withdraw_submit": "💸 *Submit Withdrawal Request*\n\nMethod: {method}\n\nPlease provide your account details:\nFormat: `Account Number | Account Holder Name`\n\nExample: `Account Number | Name`",
        "withdraw_request_sent": "✅ Withdrawal request submitted!\n\nAmount: {amount} Taka\nMethod: {method}\nAccount: {account}\n\nAdmin will verify and process soon.",
        "referral": "👥 *Referral System*\n\nYour referral link:\n`https://t.me/{bot_username}?start={code}`\n\nFor each referral, you get {bonus} Taka bonus!\nPlus {commission}% commission on their earnings!\n\nTotal Referrals: {count}\nTotal Bonus Earned: {bonus_earned} Taka",
        "wheel": "🎡 *Wheel of Fortune*\n\nSpin the wheel and win amazing prizes!\n\nSpin Cost: {cost} Taka\nYour Balance: {balance} Taka\n\nClick the button below to spin!",
        "wheel_result": "🎉 *Wheel Result*\n\nYou won: {reward} Taka!\n\nYour new balance: {balance} Taka",
        "insufficient_balance": "❌ Insufficient balance! You need {cost} Taka to spin.",
        "leaderboard": "🏆 *Leaderboard - Top Earners*\n\n{ranking}\n\nKeep earning to reach the top!",
        "language_changed": "🌐 Language changed to English!",
        "back": "◀️ Back",
        "confirm": "✅ Confirm",
        "cancel": "❌ Cancel"
    },
    "bn": {
        "welcome": "👋 স্বাগতম আর্নবটে!\n\nটাস্ক সম্পন্ন করে, বন্ধুদের রেফার করে এবং হুইল ঘুরিয়ে টাকা আয় করুন!",
        "profile": "👤 *প্রোফাইল*\n\nআইডি: `{user_id}`\nইউজারনেম: @{username}\nব্যালেন্স: 💰 {balance} টাকা\nমোট আয়: 📈 {total_earned} টাকা\nমোট উত্তোলন: 💸 {total_withdrawn} টাকা\nরেফারেল: 👥 {referrals}\nভাষা: {language}",
        "tasks": "📋 *উপলব্ধ টাস্ক*\n\nটাকা আয় করতে টাস্ক সম্পন্ন করুন!",
        "no_tasks": "❌ এই মুহূর্তে কোনো টাস্ক নেই।",
        "task_details": "📌 *{title}*\n\n{description}\n\n💰 পুরস্কার: {reward} টাকা",
        "task_completed": "✅ টাস্ক সফলভাবে সম্পন্ন হয়েছে!\n\nআপনি পেয়েছেন: {reward} টাকা",
        "task_already_completed": "❌ আপনি ইতিমধ্যে এই টাস্ক সম্পন্ন করেছেন!",
        "deposit": "💳 *টাকা জমা দিন*\n\nআপনার পেমেন্ট পদ্ধতি নির্বাচন করুন:",
        "deposit_instruction": "💰 *জমা অনুরোধ*\n\nপদ্ধতি: {method}\nপরিমাণ: {amount} টাকা\n\nঅনুগ্রহ করে {amount} টাকা পাঠান:\n{payment_info}\n\nপাঠানোর পর 'পাঠিয়েছি' ক্লিক করুন।",
        "deposit_submit": "📝 *ট্রানজেকশন তথ্য জমা দিন*\n\nঅনুগ্রহ করে পাঠান:\n1️⃣ ট্রানজেকশন আইডি\n2️⃣ পরিমাণ (যদি ভিন্ন হয়)\n3️⃣ স্ক্রিনশট (ঐচ্ছিক)\n\nফরম্যাট:\n`TXNID123456 | 500`",
        "deposit_request_sent": "✅ জমা অনুরোধ জমা দেওয়া হয়েছে!\n\nট্রানজেকশন আইডি: {txn_id}\nপরিমাণ: {amount} টাকা\n\nঅ্যাডমিন যাচাই করে অনুমোদন দিবেন।",
        "withdraw": "💸 *টাকা উত্তোলন*\n\nবর্তমান ব্যালেন্স: {balance} টাকা\nন্যূনতম: {min_amount} টাকা\nসর্বোচ্চ: {max_amount} টাকা\n\nউত্তোলন পদ্ধতি নির্বাচন করুন:",
        "withdraw_submit": "💸 *উত্তোলন অনুরোধ জমা দিন*\n\nপদ্ধতি: {method}\n\nঅনুগ্রহ করে আপনার একাউন্টের তথ্য দিন:\nফরম্যাট: `একাউন্ট নাম্বার | একাউন্ট হোল্ডারের নাম`\n\nউদাহরণ: `একাউন্ট নাম্বার | নাম`",
        "withdraw_request_sent": "✅ উত্তোলন অনুরোধ জমা দেওয়া হয়েছে!\n\nপরিমাণ: {amount} টাকা\nপদ্ধতি: {method}\nএকাউন্ট: {account}\n\nঅ্যাডমিন যাচাই করে প্রসেস করবেন।",
        "referral": "👥 *রেফারেল সিস্টেম*\n\nআপনার রেফারেল লিংক:\n`https://t.me/{bot_username}?start={code}`\n\nপ্রতিটি রেফারেলের জন্য {bonus} টাকা বোনাস!\nএবং তাদের আয়ের {commission}% কমিশন!\n\nমোট রেফারেল: {count}\nমোট বোনাস: {bonus_earned} টাকা",
        "wheel": "🎡 *ভাগ্যের চাকা*\n\nচাকা ঘুরিয়ে আকর্ষণীয় পুরস্কার জিতুন!\n\nচাকা ঘুরানোর খরচ: {cost} টাকা\nআপনার ব্যালেন্স: {balance} টাকা\n\nনিচের বাটনে ক্লিক করে চাকা ঘুরান!",
        "wheel_result": "🎉 *চাকার ফলাফল*\n\nআপনি জিতেছেন: {reward} টাকা!\n\nআপনার নতুন ব্যালেন্স: {balance} টাকা",
        "insufficient_balance": "❌ পর্যাপ্ত ব্যালেন্স নেই! চাকা ঘুরাতে {cost} টাকা প্রয়োজন।",
        "leaderboard": "🏆 *লিডারবোর্ড - শীর্ষ উপার্জনকারী*\n\n{ranking}\n\nশীর্ষে পৌঁছাতে উপার্জন চালিয়ে যান!",
        "language_changed": "🌐 ভাষা বাংলায় পরিবর্তন করা হয়েছে!",
        "back": "◀️ পেছনে",
        "confirm": "✅ নিশ্চিত",
        "cancel": "❌ বাতিল"
    }
}

# ==================== DATABASE ====================
class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[DATABASE_NAME]
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.tasks = self.db.tasks
        self.payment_methods = self.db.payment_methods
        self.withdrawals = self.db.withdrawals
        self.admins = self.db.admins
        self.settings = self.db.settings

    async def init(self):
        await self.users.create_index("user_id", unique=True)
        await self.users.create_index("referral_code", unique=True)
        await self.transactions.create_index("txn_id", unique=True)
        
        # Default settings
        if not await self.settings.find_one({"_id": "system"}):
            await self.settings.insert_one({
                "_id": "system",
                "maintenance": False,
                "captcha_enabled": True,
                "min_withdraw": MIN_WITHDRAW,
                "max_withdraw": MAX_WITHDRAW,
                "referral_bonus": REFERRAL_BONUS,
                "referral_commission": 10,
                "wheel_cost": 10
            })
        
        # Default payment methods
        for method in PAYMENT_METHODS:
            if not await self.payment_methods.find_one({"id": method["id"]}):
                await self.payment_methods.insert_one({
                    **method,
                    "number": "",
                    "wallet": "",
                    "details": {}
                })

    async def get_user(self, user_id: int):
        return await self.users.find_one({"user_id": user_id})

    async def create_user(self, user_data: dict):
        return await self.users.insert_one(user_data)

    async def update_user(self, user_id: int, data: dict):
        data["last_active"] = datetime.now()
        return await self.users.update_one({"user_id": user_id}, {"$set": data})

    async def update_balance(self, user_id: int, amount: float, add: bool = True):
        if add:
            return await self.users.update_one(
                {"user_id": user_id},
                {"$inc": {"balance": amount, "total_earned": amount}}
            )
        else:
            return await self.users.update_one(
                {"user_id": user_id},
                {"$inc": {"balance": -amount, "total_withdrawn": amount}}
            )

    async def add_transaction(self, data: dict):
        return await self.transactions.insert_one(data)

    async def get_tasks(self):
        return await self.tasks.find({"active": True}).to_list(None)

    async def get_task(self, task_id: str):
        return await self.tasks.find_one({"task_id": task_id})

    async def create_task(self, data: dict):
        return await self.tasks.insert_one(data)

    async def update_task(self, task_id: str, data: dict):
        return await self.tasks.update_one({"task_id": task_id}, {"$set": data})

    async def delete_task(self, task_id: str):
        return await self.tasks.delete_one({"task_id": task_id})

    async def get_payment_methods(self):
        return await self.payment_methods.find({"active": True}).to_list(None)

    async def get_payment_method(self, method_id: str):
        return await self.payment_methods.find_one({"id": method_id})

    async def update_payment_method(self, method_id: str, data: dict):
        return await self.payment_methods.update_one({"id": method_id}, {"$set": data})

    async def add_withdrawal(self, data: dict):
        return await self.withdrawals.insert_one(data)

    async def get_withdrawals(self, status=None):
        query = {}
        if status:
            query["status"] = status
        return await self.withdrawals.find(query).sort("created_at", -1).to_list(None)

    async def get_pending_deposits(self):
        return await self.transactions.find({"type": "deposit", "status": "pending"}).to_list(None)

    async def is_admin(self, user_id: int):
        admin = await self.admins.find_one({"user_id": user_id})
        return admin is not None or user_id == ADMIN_ID

    async def add_admin(self, user_id: int, added_by: int):
        return await self.admins.insert_one({"user_id": user_id, "added_by": added_by, "added_at": datetime.now()})

    async def get_settings(self):
        return await self.settings.find_one({"_id": "system"})

    async def update_settings(self, data: dict):
        return await self.settings.update_one({"_id": "system"}, {"$set": data})

    async def get_stats(self):
        total_users = await self.users.count_documents({})
        active_users = await self.users.count_documents({"status": "active"})
        total_balance = await self.users.aggregate([{"$group": {"_id": None, "total": {"$sum": "$balance"}}}]).to_list(None)
        total_earned = await self.users.aggregate([{"$group": {"_id": None, "total": {"$sum": "$total_earned"}}}]).to_list(None)
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_balance": total_balance[0]["total"] if total_balance else 0,
            "total_earned": total_earned[0]["total"] if total_earned else 0
        }

# ==================== STATES ====================
class DepositState(StatesGroup):
    selecting_method = State()
    entering_amount = State()
    submitting_txn = State()

class WithdrawState(StatesGroup):
    selecting_method = State()
    entering_amount = State()
    submitting_details = State()

class AdminState(StatesGroup):
    broadcast = State()
    add_task = State()
    edit_task = State()
    add_payment = State()
    edit_payment = State()
    search_user = State()
    edit_balance = State()

# ==================== KEYBOARDS ====================
class Keyboards:
    @staticmethod
    def main_menu(lang: str):
        texts = TEXTS[lang]
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📋 Tasks", callback_data="menu_tasks"),
            InlineKeyboardButton(text="👤 Profile", callback_data="menu_profile")
        )
        builder.row(
            InlineKeyboardButton(text="💳 Deposit", callback_data="menu_deposit"),
            InlineKeyboardButton(text="💸 Withdraw", callback_data="menu_withdraw")
        )
        builder.row(
            InlineKeyboardButton(text="👥 Referral", callback_data="menu_referral"),
            InlineKeyboardButton(text="🎡 Wheel", callback_data="menu_wheel")
        )
        builder.row(
            InlineKeyboardButton(text="🏆 Leaderboard", callback_data="menu_leaderboard"),
            InlineKeyboardButton(text="🌐 Language", callback_data="menu_language")
        )
        return builder.as_markup()

    @staticmethod
    def back_button(lang: str):
        texts = TEXTS[lang]
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=texts["back"], callback_data="menu_main")]
        ])

    @staticmethod
    def payment_methods(lang: str, methods: list):
        builder = InlineKeyboardBuilder()
        for method in methods:
            builder.row(InlineKeyboardButton(
                text=f"💳 {method['name']}",
                callback_data=f"deposit_method_{method['id']}"
            ))
        builder.row(InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="menu_main"))
        return builder.as_markup()

    @staticmethod
    def withdraw_methods(lang: str, methods: list):
        builder = InlineKeyboardBuilder()
        for method in methods:
            builder.row(InlineKeyboardButton(
                text=f"💸 {method['name']}",
                callback_data=f"withdraw_method_{method['id']}"
            ))
        builder.row(InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="menu_main"))
        return builder.as_markup()

    @staticmethod
    def admin_panel():
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="👥 Users", callback_data="admin_users"),
            InlineKeyboardButton(text="💰 Finance", callback_data="admin_finance")
        )
        builder.row(
            InlineKeyboardButton(text="📋 Tasks", callback_data="admin_tasks"),
            InlineKeyboardButton(text="💳 Payments", callback_data="admin_payments")
        )
        builder.row(
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="admin_settings")
        )
        builder.row(
            InlineKeyboardButton(text="👑 Admins", callback_data="admin_admins"),
            InlineKeyboardButton(text="📊 Stats", callback_data="admin_stats")
        )
        builder.row(InlineKeyboardButton(text="◀️ Back", callback_data="menu_main"))
        return builder.as_markup()

# ==================== UTILITIES ====================
def generate_referral_code(user_id: int) -> str:
    return hashlib.md5(f"{user_id}{datetime.now()}".encode()).hexdigest()[:8]

def generate_txn_id() -> str:
    return f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

def generate_captcha() -> str:
    return ''.join(random.choices(string.digits, k=6))

def format_amount(amount: float) -> str:
    return f"{amount:,.2f}"

# ==================== BOT HANDLERS ====================
class EarnBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.db = Database()
        self.keyboards = Keyboards()

    async def start(self):
        await self.db.init()
        
        # Register handlers
        self.dp.message.register(self.cmd_start, CommandStart())
        self.dp.message.register(self.handle_text)
        self.dp.callback_query.register(self.handle_callback)
        
        # Admin commands
        self.dp.message.register(self.cmd_admin, Command("admin"))
        
        logging.basicConfig(level=logging.INFO)
        await self.dp.start_polling(self.bot)

    async def get_user_lang(self, user_id: int) -> str:
        user = await self.db.get_user(user_id)
        return user.get("language", "en") if user else "en"

    async def get_text(self, user_id: int, key: str, **kwargs) -> str:
        lang = await self.get_user_lang(user_id)
        text = TEXTS[lang].get(key, TEXTS["en"][key])
        return text.format(**kwargs) if kwargs else text

    async def cmd_start(self, message: Message, state: FSMContext):
        user_id = message.from_user.id
        username = message.from_user.username or "NoUsername"
        
        user = await self.db.get_user(user_id)
        
        if not user:
            # New user - captcha check
            captcha = generate_captcha()
            await state.update_data(captcha=captcha, attempts=0)
            
            await message.answer(
                f"🤖 *Verification*\n\nPlease enter the code below to verify you're human:\n\n"
                f"`{captcha}`\n\n"
                f"You have 3 attempts.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Verify", callback_data="verify_captcha")]
                ])
            )
            await state.set_state("captcha")
            return
        
        # Check if user is banned
        if user.get("status") == "banned":
            await message.answer("❌ You are banned from using this bot.")
            return
        
        # Welcome message
        text = await self.get_text(user_id, "welcome")
        await message.answer(text, reply_markup=self.keyboards.main_menu(await self.get_user_lang(user_id)))
        await self.db.update_user(user_id, {"last_active": datetime.now()})

    async def handle_callback(self, callback: CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        data = callback.data
        
        if data == "menu_main":
            text = await self.get_text(user_id, "welcome")
            await callback.message.edit_text(text, reply_markup=self.keyboards.main_menu(await self.get_user_lang(user_id)))
        
        elif data == "menu_profile":
            await self.show_profile(callback)
        
        elif data == "menu_tasks":
            await self.show_tasks(callback)
        
        elif data == "menu_deposit":
            await self.show_deposit(callback, state)
        
        elif data == "menu_withdraw":
            await self.show_withdraw(callback, state)
        
        elif data == "menu_referral":
            await self.show_referral(callback)
        
        elif data == "menu_wheel":
            await self.show_wheel(callback)
        
        eli
