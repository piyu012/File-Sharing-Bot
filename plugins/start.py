from aiohttp import web
from plugins import web_server
import pyromod.listen
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
import sys
from datetime import datetime
from config import (
    API_HASH, API_ID, LOGGER, BOT_TOKEN, TG_BOT_WORKERS,
    FORCE_SUB_CHANNEL, CHANNEL_ID, PORT, DB_URL, DB_NAME
)
import pyrogram.utils
from pymongo import MongoClient
import time
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

pyrogram.utils.MIN_CHANNEL_ID = -1009999999999

# --- MongoDB Connection ---
client = MongoClient(DB_URL)
db = client[DB_NAME]
tokens = db["access_tokens"]  # नया collection access_tokens

# --- Token System ---
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

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="Bot",
            api_hash=API_HASH,
            api_id=API_ID,
            plugins={"root": "plugins"},
            workers=TG_BOT_WORKERS,
            bot_token=BOT_TOKEN
        )
        self.LOGGER = LOGGER

    async def start(self):
        await super().start()
        usr_bot_me = await self.get_me()
        self.uptime = datetime.now()

        # --- Force Sub Setup ---
        if FORCE_SUB_CHANNEL:
            try:
                link = (await self.get_chat(FORCE_SUB_CHANNEL)).invite_link
                if not link:
                    await self.export_chat_invite_link(FORCE_SUB_CHANNEL)
                    link = (await self.get_chat(FORCE_SUB_CHANNEL)).invite_link
                self.invitelink = link
            except Exception as a:
                self.LOGGER(__name__).warning(a)
                self.LOGGER(__name__).warning("Bot Can't Export Invite link From Force Sub Channel!")
                self.LOGGER(__name__).info("Please check FORCE_SUB_CHANNEL value.")
                sys.exit()

        # --- DB Channel Test ---
        try:
            db_channel = await self.get_chat(CHANNEL_ID)
            self.db_channel = db_channel
            test = await self.send_message(chat_id=db_channel.id, text="Hey 🖐")
            await test.delete()
        except Exception as e:
            self.LOGGER(__name__).warning(e)
            self.LOGGER(__name__).warning("Make Sure Bot Is Admin In DB Channel")
            sys.exit()

        self.set_parse_mode(ParseMode.HTML)
        self.LOGGER(__name__).info(f"Bot Running...!\n\nCreated By https://t.me/Madflix_Bots")
        self.LOGGER(__name__).info(f"ミ💖 MADFLIX BOTZ 💖彡")
        self.username = usr_bot_me.username

        # --- Web Server Start ---
        app = web.AppRunner(await web_server())
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()

        # --- Token Based Access System ---
        @self.on_message(filters.command("start"))
        async def start_command(_, message):
            user_id = message.from_user.id

            # अगर user के पास valid token नहीं है
            if not is_token_valid(user_id):
                ad_link = "https://your-ad-link.example.com"  # 👈 यहां अपना ad link डालो
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

            # ✅ अगर टोकन valid है तो बॉट का main content दिखाओ
            buttons = [
                [InlineKeyboardButton("📂 Upload File", callback_data="upload")],
                [InlineKeyboardButton("🔍 Search Files", callback_data="search")],
                [InlineKeyboardButton("ℹ️ About", callback_data="about")]
            ]

            await message.reply_text(
                f"🎉 <b>Welcome to MADFLIX BOTZ!</b>\n\n"
                f"नमस्ते <b>{message.from_user.first_name}</b> 👋\n\n"
                "आपका एक्सेस वैध है ✅\n"
                "अब आप बॉट का इस्तेमाल कर सकते हैं।\n\n"
                "👇 नीचे से एक ऑप्शन चुनें:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__).info("Bot Stopped...")
