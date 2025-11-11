from pyrogram import Client, filters
from pymongo import MongoClient
from config import DB_URL, DB_NAME
import time

# MongoDB Setup
client = MongoClient(DB_URL)
db = client[DB_NAME]
tokens = db["access_tokens"]

@Client.on_message(filters.command("status"))
async def status_command(client, message):
    user_id = message.from_user.id
    user = tokens.find_one({"user_id": user_id})

    if not user:
        await message.reply_text("❌ आपका कोई Active Token नहीं मिला।\n/start करके नया Token प्राप्त करें 🔐")
        return

    expiry = user.get("expiry", 0)
    remaining = int(expiry - time.time())

    if remaining <= 0:
        await message.reply_text("⛔ आपका Token Expire हो चुका है!\n/start करके नया Token प्राप्त करें 🔁")
    else:
        mins = remaining // 60
        secs = remaining % 60
        await message.reply_text(
            f"✅ <b>Token Active है!</b>\n\n⏳ शेष समय: <b>{mins} मिनट {secs} सेकंड</b>",
            disable_web_page_preview=True
        )
