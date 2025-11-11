from pyrogram import Client, filters
import time
from pymongo import MongoClient
from config import DB_URL, DB_NAME

client = MongoClient(DB_URL)
db = client[DB_NAME]
tokens = db["access_tokens"]

def is_token_valid(user_id: int):
    user = tokens.find_one({"user_id": user_id})
    if not user:
        return False
    expiry = user["expiry"]
    return time.time() < expiry

def renew_token(user_id: int):
    expiry_time = time.time() + 24 * 60 * 60  # 24 घंटे
    tokens.update_one(
        {"user_id": user_id},
        {"$set": {"expiry": expiry_time}},
        upsert=True
    )

@Client.on_message(filters.command("start"))
async def start_command(_, message):
    user_id = message.from_user.id
    if not is_token_valid(user_id):
        ad_link = "https://your-ad-link.example.com"  # 🔗 यहां अपना Ad लिंक डालो
        text = (
            "🔒 <b>Access Token Required</b>\n\n"
            "आपका टोकन expire हो चुका है या अभी बना नहीं है।\n\n"
            "👇 नीचे दिए लिंक पर क्लिक करके ad देखो और नया टोकन लो:\n\n"
            f"<a href='{ad_link}'>🎥 Watch Ad & Renew Token</a>\n\n"
            "टोकन valid रहेगा 24 घंटे तक।"
        )
        await message.reply_text(text, disable_web_page_preview=False)
        renew_token(user_id)
    else:
        await message.reply_text(
            "✅ <b>Access Granted!</b>\nआपका टोकन अभी वैध है, आप बॉट का इस्तेमाल कर सकते हैं।"
        )
