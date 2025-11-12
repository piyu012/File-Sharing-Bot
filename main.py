import asyncio
from bot import Bot
from aiohttp import web
from plugins import web_server
import dns.resolver

# --- DNS Fix for Render ---
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']

# --- Function to start everything ---
async def main():
    # Start the Web Server
    app = await web_server()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)  # 8080 default for Render
    await site.start()

    # Start the Telegram Bot
    bot = Bot()
    await bot.start()

    print("🚀 Both Web Server & Telegram Bot are Running!")

    # Run forever
    await asyncio.Event().wait()

# --- Run the whole system ---
if __name__ == "__main__":
    asyncio.run(main())
