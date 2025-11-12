import asyncio
import threading
from aiohttp import web
from bot import Bot
from plugins import web_server
import dns.resolver

# DNS Fix for Render
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ["8.8.8.8", "1.1.1.1"]

# Web server run karega alag thread me
async def start_web():
    app = await web_server()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("🌐 Web server started on port 8080")
    await asyncio.Event().wait()

def run_web_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_web())

# Telegram Bot run karega apne loop me
async def start_bot():
    bot = Bot()
    await bot.start()
    print("🤖 Telegram bot started successfully!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    # web ko alag thread me run karo
    web_thread = threading.Thread(target=run_web_in_thread, daemon=True)
    web_thread.start()

    # aur bot ko apne main loop me
    asyncio.run(start_bot())
