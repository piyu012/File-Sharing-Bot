import asyncio
from aiohttp import web
from bot import Bot
import dns.resolver

# ✅ DNS fix
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ["8.8.8.8", "1.1.1.1"]

# ✅ Web server setup
async def handle_root(request):
    return web.Response(text="✅ Bot server running on Render!")

async def handle_verify(request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        token = data.get("token")

        if not user_id or not token:
            return web.json_response({"status": "error", "message": "Missing parameters"}, status=400)

        if token == "my_secret_token":
            print(f"✅ Verified user: {user_id}")
            return web.json_response({"status": "ok", "message": "Verification successful"})
        else:
            return web.json_response({"status": "error", "message": "Invalid token"}, status=401)

    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_post("/verify", handle_verify)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("🌐 Web server started on port 8080")

# ✅ Main bot + web startup
async def main():
    bot = Bot()
    await bot.start()
    print("🤖 Bot started")

    # Run web server in same event loop
    await web_server()

    # Keep alive
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
