from aiohttp import web
from pymongo import MongoClient
import time
import os

DB_URL = os.getenv("DB_URL")
DB_NAME = os.getenv("DB_NAME")

client = MongoClient(DB_URL)
db = client[DB_NAME]
tokens = db["access_tokens"]

async def renew_token(request):
    data = await request.json()
    user_id = int(data["user_id"])
    expiry_time = time.time() + 24 * 60 * 60  # 24 घंटे
    tokens.update_one(
        {"user_id": user_id},
        {"$set": {"expiry": expiry_time}},
        upsert=True
    )
    return web.json_response({"status": "success", "expiry": expiry_time})

app = web.Application()
app.router.add_post("/renew", renew_token)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
