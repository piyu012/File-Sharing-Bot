from aiohttp import web
from plugins import web_server
import pyromod.listen
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
import sys, time
from datetime import datetime
from pymongo import MongoClient
from config import (
    API_HASH, API_ID, LOGGER, BOT_TOKEN, TG_BOT_WORKERS,
    FORCE_SUB_CHANNEL, CHANNEL_ID, PORT, DB_URL, DB_NAME
)
import pyrogram.utils

pyrogram.utils.MIN_CHANNEL_ID = -1009999999999

# --- MongoDB Connection ---
client = MongoClient(DB_URL)
db = client[DB_NAME]
tokens = db["access_tokens"]  # access_tokens collection

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
        self.username = usr_bot_me.username
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

        # --- Channel Check ---
        try:
            db_channel = await self.get_chat(CHANNEL_ID)
            self.db_channel = db_channel
            test = await self.send_message(chat_id=db_channel.id, text="✅ Bot Connected To Channel")
            await test.delete()
        except Exception as e:
            self.LOGGER(__name__).warning(e)
            self.LOGGER(__name__).warning("❌ Make Sure Bot Is Admin In Channel")
            sys.exit()

        self.set_parse_mode(ParseMode.HTML)
        self.LOGGER(__name__).info(f"Bot Started as @{self.username}")

        # --- Web Server Start ---
        app = web.AppRunner(await web_server())
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()

        # --- Main Command ---
        @self.on_message(filters.command("start"))
        async def start_command(_, message):
            user_id = message.from_user.id

            # Token check
            if not is_token_valid(user_id):
                ad_link = "https://your-ad-link.example.com"  # 👈 यहां अपना ad link भरो
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

            # Valid Token → Send content
            await message.reply_text("✅ <b>Access Granted!</b>\nआपका टोकन valid है — content भेजा जा रहा है...")

            try:
                async for msg in self.get_chat_history(CHANNEL_ID, limit=3):  # कितने message भेजने हैं
                    if msg.text:
                        await message.reply_text(msg.text)
                    elif msg.photo:
                        await message.reply_photo(msg.photo.file_id, caption=msg.caption or "")
                    elif msg.video:
                        await message.reply_video(msg.video.file_id, caption=msg.caption or "")
                    elif msg.document:
                        await message.reply_document(msg.document.file_id, caption=msg.caption or "")
            except Exception as e:
                await message.reply_text(f"⚠️ Error fetching content: <code>{e}</code>")

    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__).info("Bot Stopped...")
