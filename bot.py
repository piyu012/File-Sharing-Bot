from aiohttp import web
import os, sys, json, time
from datetime import datetime
import pyromod.listen
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import pyrogram.utils

# ---- CONFIG (Render env) ----
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
FORCE_SUB_CHANNEL = int(os.getenv("FORCE_SUB_CHANNEL", "0"))  # 0 to disable
TG_BOT_WORKERS = int(os.getenv("TG_BOT_WORKERS", "4"))
PORT = int(os.getenv("PORT", "10000"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-render-app.onrender.com/static/index.html")

pyrogram.utils.MIN_CHANNEL_ID = -1009999999999

# ---- Simple token store (replace with Redis/Mongo TTL in prod) ----
TOKENS: dict[int, float] = {}  # {user_id: expiry_ts}  # keep minimal PoC [web:18]
def has_valid_token(uid: int) -> bool:
    return TOKENS.get(uid, 0) > time.time()  # [web:18]

def renew_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Renew Access Token", web_app=WebAppInfo(url=WEBAPP_URL))],  # [web:82][web:32]
            [InlineKeyboardButton("Try Again", callback_data="try_again")]
        ]
    )

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="Bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=TG_BOT_WORKERS,
            plugins={"root": "plugins"}
        )
        self.LOGGER = print

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username = me.username
        self.uptime = datetime.now()

        # ForceSub: prefetch invite link if enabled
        if FORCE_SUB_CHANNEL:
            try:
                link = (await self.get_chat(FORCE_SUB_CHANNEL)).invite_link
                if not link:
                    await self.export_chat_invite_link(FORCE_SUB_CHANNEL)
                    link = (await self.get_chat(FORCE_SUB_CHANNEL)).invite_link
                self.invitelink = link
            except Exception as e:
                self.LOGGER(f"[ForceSub] invite link error: {e}")
                sys.exit(1)  # [web:18]

        # DB channel sanity
        try:
            db_channel = await self.get_chat(CHANNEL_ID)
            self.db_channel = db_channel
            t = await self.send_message(db_channel.id, "Hey 🖐")
            await t.delete()
        except Exception as e:
            self.LOGGER(f"[DB] channel check failed: {e}")
            sys.exit(1)  # [web:18]

        self.set_parse_mode(ParseMode.HTML)

        # ---- aiohttp: serve / and /static for Mini App ----
        app = web.Application()
        static_dir = os.path.join(os.getcwd(), "static")
        async def root(_):
            return web.FileResponse(path=os.path.join(static_dir, "index.html"))  # [web:77][web:87]
        app.router.add_get("/", root)
        app.router.add_static("/static/", path=static_dir, name="static")  # [web:87]
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORT).start()  # Render binds $PORT [web:94]

        # ---- Commands/Handlers ----
        @self.on_message(filters.command("start") & filters.private)
        async def start_cmd(_, m):
            # If deep-link payload present, gating will happen in plugins/start.py
            if len(m.command) == 1:
                txt = (
                    "Your Access Token has expired. Please renew it and try again.

"
                    "Token Validity: 24 hours

"
                    "This is an ads-based access token. Complete one ad to unlock sharable links for 24 hours."
                )
                await m.reply_text(txt, reply_markup=renew_kb())  # [web:32]

        # Receive Mini App result
        @self.on_message(filters.web_app_data & filters.private)
        async def on_webapp_data(_, m):
            try:
                data = json.loads(m.web_app_data.data or "{}")
            except Exception:
                data = {}
            if data.get("event") == "rewarded_ok":
                TOKENS[m.from_user.id] = time.time() + 24 * 3600
                await m.reply_text("✅ Access granted for next 24 hours.")
            else:
                await m.reply_text("❌ Reward not completed. Please try again.", reply_markup=renew_kb())  # [web:72][web:32]

        # Example gated command for quick test
        @self.on_message(filters.command("get") & filters.private)
        async def get_demo(_, m):
            if not has_valid_token(m.from_user.id):
                return await m.reply_text("⛔ Token expired. Renew to continue.", reply_markup=renew_kb())  # [web:18]
            await m.reply_text("Here is your protected content ✅")

    async def stop(self, *args):
        await super().stop()
        self.LOGGER("Bot Stopped...")

if __name__ == "__main__":
    import asyncio
    asyncio.run(Bot().start())
