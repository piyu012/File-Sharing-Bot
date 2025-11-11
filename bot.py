from aiohttp import web
from plugins import web_server
import pyromod.listen
from pyrogram import Client
from pyrogram.enums import ParseMode
import sys
from datetime import datetime
from config import API_HASH, API_ID, LOGGER, BOT_TOKEN, TG_BOT_WORKERS, FORCE_SUB_CHANNEL, CHANNEL_ID, PORT
import pyrogram.utils
from pymongo import MongoClient
import time
from pyrogram import filters

pyrogram.utils.MIN_CHANNEL_ID = -1009999999999

# --- MongoDB Setup ---
MONGO_URI = "YOUR_MONGO_URI"  # 👈 यहां अपनी MongoDB connection URI डालो
DB_NAME = "MadflixDB"
COLLECTION = "access_tokens"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
tokens = db[COLLECTION]

def is_token_valid(user_id: int):
    user = tokens.find_one({"user_id": user_id})
    if not user:
        return False
    expiry = user["expiry"]
    return time.time() < expiry

def renew_token(user_id: int):
    expiry_time = time.time() + 24 * 60 * 60  # 24 hours validity
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
                self.LOGGER(__name__).warning(f"Please Double Check The FORCE_SUB_CHANNEL Value And Make Sure Bot Is Admin In Channel With Invite Users Via Link Permission, Current Force Sub Channel Value: {FORCE_SUB_CHANNEL}")
                self.LOGGER(__name__).info("\nBot Stopped. https://t.me/MadflixBots_Support For Support")
                sys.exit()

        try:
            db_channel = await self.get_chat(CHANNEL_ID)
            self.db_channel = db_channel
            test = await self.send_message(chat_id=db_channel.id, text="Hey 🖐")
            await test.delete()
        except Exception as e:
            self.LOGGER(__name__).warning(e)
            self.LOGGER(__name__).warning(f"Make Sure Bot Is Admin In DB Channel, And Double Check The CHANNEL_ID Value, Current Value: {CHANNEL_ID}")
            self.LOGGER(__name__).info("\nBot Stopped. Join https://t.me/MadflixBots_Support For Support")
            sys.exit()

        self.set_parse_mode(ParseMode.HTML)
        self.LOGGER(__name__).info(f"Bot Running...!\n\nCreated By \nhttps://t.me/Madflix_Bots")
        self.LOGGER(__name__).info(f"""ミ💖 MADFLIX BOTZ 💖彡""")
        self.username = usr_bot_me.username

        # Web Server
        app = web.AppRunner(await web_server())
        await app.setup()
        bind_address = "0.0.0.0"
        await web.TCPSite(app, bind_address, PORT).start()

        # Register token system handlers
        @self.on_message(filters.command("start"))
        async def start_command(_, message):
            user_id = message.from_user.id
            if not is_token_valid(user_id):
                ad_link = "https://your-ad-link.example.com"  # 👈 यहां अपना ad link डालो
                text = (
                    "🔒 <b>Access Token Required</b>\n\n"
                    "Your token has expired or not found.\n"
                    "Watch an ad and renew your token to access the bot.\n\n"
                    f"<a href='{ad_link}'>🎥 Watch Ad & Renew Token</a>"
                )
                await message.reply_text(text, disable_web_page_preview=False)
                renew_token(user_id)
            else:
                await message.reply_text("✅ <b>Access Granted!</b>\nYou already have a valid token for 24 hours.")

    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__).info("Bot Stopped...")
