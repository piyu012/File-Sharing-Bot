import pymongo, certifi, dns.resolver, os
from config import DB_URL, DB_NAME

# Termux DNS fix
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8','1.1.1.1']

dbclient = pymongo.MongoClient(DB_URL, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=30000)
db = dbclient[DB_NAME]
user_data = db["users"]

async def add_user(user_id:int):
    user_data.update_one({"_id": user_id}, {"$setOnInsert":{"_id": user_id}}, upsert=True)

async def del_user(user_id:int):
    user_data.delete_one({"_id": user_id})

async def present_user(user_id:int) -> bool:
    return user_data.find_one({"_id": user_id}) is not None

async def full_userbase():
    return [u["_id"] for u in user_data.find({}, {"_id":1})]
