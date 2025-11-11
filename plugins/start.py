from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import time
from pymongo import MongoClient
from config import DB_URL, DB_NAME

# 🔹 MongoDB setup
client = MongoClient(DB_URL)
db = client[DB_NAME]
tokens = db["access_tokens"]

# 🔹 Token validity check
def is_token_valid(user_id: int):
    user = tokens.find_one({"user_id": user_id})
    if not user:
        return False
    expiry = user["expiry"]
    return time.time() < expiry

# 🔹 Token renewal
def renew_token(user_id: int):
    expiry_time = time.time() + 24 * 60 * 60  # 24 घंटे
    tokens.update_one(
        {"user_id": user_id},
        {"$set": {"expiry": expiry_time}},
        upsert=True
    )

# 🔹 /start Command
@Client.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id

    # 🔸 अगर टोकन invalid है, तो पहले Ad link दिखाओ
    if not is_token_valid(user_id):
        ad_link = "https://your-ad-link.example.com"  # ← यहां अपना Ad link डालो
        text = (
            "🔒 <b>Access Token Required</b>\n\n"
            "आपका टोकन expire हो चुका है या अभी बना नहीं है।\n\n"
            "👇 नीचे दिए लिंक पर क्लिक करके ad देखो और नया टोकन लो:\n\n"
            f"<a href='{ad_link}'>🎥 Watch Ad & Renew Token</a>\n\n"
            "टोकन valid रहेगा 24 घंटे तक।"
        )
        await message.reply_text(text, disable_web_page_preview=False)
        renew_token(user_id)
        return

    # 🔸 अगर टोकन valid है → पुराना content दिखाओ
    buttons = [[
        InlineKeyboardButton('📢 Update Channel', url='https://t.me/YourChannel'),
        InlineKeyboardButton('🧩 Support Group', url='https://t.me/YourSupportGroup')
    ], [
        InlineKeyboardButton('➕ Add Me To Your Group', url=f'http://t.me/{client.me.username}?startgroup=true')
    ]]

    text = (
        f"👋 Hello {message.from_user.first_name}!\n\n"
        "मैं एक File Store Bot हूँ 📁\n\n"
        "आप मुझे कोई भी फ़ाइल भेज सकते हैं और मैं आपको उसका लिंक दे दूँगा "
        "जिससे कोई भी डाउनलोड कर सकेगा 🔗"
    )

    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )
