from aiohttp import web
from plugins import web_server
import pyromod.listen
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
import sys
from datetime import datetime
from config import API_HASH, API_ID, LOGGER, BOT_TOKEN, TG_BOT_WORKERS, FORCE_SUB_CHANNEL, CHANNEL_ID, PORT, DB_URL, DB_NAME
import pyrogram.utils
from pymongo import MongoClient
import time

pyrogram.utils.MIN_CHANNEL_ID = -1009999999999

# --- MongoDB Connection ---
client = MongoClient(DB_URL)
db = client[DB_NAME]
tokens = db["access_tokens"]

# --- Token System ---
def is_token_valid(user_id: int):
    user = tokens.find_one({"user_id": user_id})
    if not user:
        return False
    expiry = user["expiry"]
    return time.time() < expiry

def renew_token(user_id: int, minutes=2):
    expiry_time = time.time() + (minutes * 60)
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
        self.username = usr_bot_me.username
        self.LOGGER(__name__).info(f"Bot Running... | @{self.username}")

        # --- Web Server Start ---
        app = web.AppRunner(await web_server())
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()

        # --- Start Command (Token + Ad) ---
        @self.on_message(filters.command("start"))
        async def start_command(_, message):
            user_id = message.from_user.id
            if not is_token_valid(user_id):
                ad_link = "https://example.com/watch-ad"  # Random ad link
                text = (
                    "🎯 <b>Access Token Required</b>\n\n"
                    "आपका टोकन expire हो चुका है या अभी बना नहीं है।\n\n"
                    "👇 नीचे दिए लिंक पर क्लिक करें और ad देखें ताकि नया टोकन मिले:\n\n"
                    f"<a href='{ad_link}'>🎬 Watch Ad & Unlock Access</a>\n\n"
                    "🕒 टोकन valid रहेगा <b>2 मिनट</b> तक।"
                )
                await message.reply_text(text, disable_web_page_preview=False)
                renew_token(user_id, 2)
            else:
                await message.reply_text(
                    "✅ <b>Access Granted!</b>\nअब आप बॉट से content प्राप्त कर सकते हैं।",
                    disable_web_page_preview=True
                )

    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__).info("Bot Stopped...")
