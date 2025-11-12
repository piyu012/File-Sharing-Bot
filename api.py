# api.py
from aiohttp import web
from datetime import datetime
import time
from pymongo import MongoClient
from config import DB_URL, DB_NAME

client = MongoClient(DB_URL)
db = client[DB_NAME]
ads = db["ad_views"]

# ✅ Route: User opens ad link
async def ad_view(request):
    uid = request.query.get("uid")
    code = request.query.get("code")

    if not uid or not code:
        return web.Response(text="❌ Invalid ad link.")

    ads.update_one(
        {"user_id": int(uid)},
        {"$set": {"viewed": True, "view_time": time.time(), "code": code}},
        upsert=True
    )
    return web.Response(text="✅ Ad viewed successfully. You can now return to Telegram and verify!")

# ✅ Optional check endpoint
async def check_view(request):
    uid = request.query.get("uid")
    user = ads.find_one({"user_id": int(uid)})
    if not user:
        return web.json_response({"viewed": False})
    return web.json_response({"viewed": user.get("viewed", False)})

# ✅ Function to include routes
async def setup_routes(app):
    app.router.add_get("/ad", ad_view)
    app.router.add_get("/check", check_view)
    return app
