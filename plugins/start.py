import asyncio, humanize, logging, random, time
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from bot import Bot
from config import ADMINS, FORCE_MSG, START_MSG, CUSTOM_CAPTION, DISABLE_CHANNEL_BUTTON, PROTECT_CONTENT, FILE_AUTO_DELETE
from helper_func import subscribed, decode, get_messages
from database.database import add_user, del_user, full_userbase, present_user

log = logging.getLogger("start")
file_auto_delete = humanize.naturaldelta(FILE_AUTO_DELETE)

# Memory-based token storage
user_tokens = {}

# Random ad links (you can replace these with your real links)
ad_links = [
    "https://your-ad-link1.example.com",
    "https://your-ad-link2.example.com",
    "https://your-ad-link3.example.com"
]

def generate_token(user_id):
    token = f"TOKEN-{user_id}-{int(time.time())}"
    user_tokens[user_id] = {
        "token": token,
        "expiry": time.time() + 120  # 2 minutes
    }
    return token

def is_token_valid(user_id):
    if user_id not in user_tokens:
        return False
    token_data = user_tokens[user_id]
    if time.time() > token_data["expiry"]:
        del user_tokens[user_id]
        return False
    return True

def get_payload(text: str):
    parts = text.split(maxsplit=1)
    return parts[1] if len(parts) == 2 else None


@Bot.on_message(filters.command('start') & filters.private & subscribed)
async def start_command(client: Client, message: Message):
    uid = message.from_user.id

    if not await present_user(uid):
        try:
            await add_user(uid)
        except Exception as e:
            log.warning("add_user failed: %s", e)

    payload = get_payload(message.text)

    # --- TOKEN CHECK ---
    if not is_token_valid(uid):
        random_ad = random.choice(ad_links)
        token = generate_token(uid)
        btn = [[InlineKeyboardButton("🎥 Watch Ad & Verify Access", url=random_ad)]]
        await message.reply_text(
            f"🔒 <b>Access Locked</b>\n\nआपका access token expire हो गया है या मौजूद नहीं है।\n"
            f"👇 नीचे दिए लिंक पर क्लिक करें और ad देखने के बाद दोबारा /start भेजें।\n\n"
            f"Token valid रहेगा: <b>2 मिनट</b> तक।",
            reply_markup=InlineKeyboardMarkup(btn),
            disable_web_page_preview=False
        )
        return

    # --- NORMAL START (User has valid token) ---
    if not payload:
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("😊 About Me", callback_data="about"),
              InlineKeyboardButton("🔒 Close", callback_data="close")]]
        )
        return await message.reply_text(
            text=START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=uid
            ),
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            quote=True
        )

    # --- Deep-link decode ---
    try:
        decoded = await decode(payload)
    except Exception as e:
        log.exception("decode failed: %s", e)
        return await message.reply_text("Invalid or expired link.")

    args = decoded.split("-")
    mul = abs(client.db_channel.id)

    ids = []
    try:
        if len(args) == 3:
            s_raw = int(args[1])
            e_raw = int(args[2])
            if s_raw % mul != 0 or e_raw % mul != 0:
                raise ValueError("token tampered")
            start = s_raw // mul
            end = e_raw // mul
            ids = range(start, end + 1) if start <= end else list(range(start, end - 1, -1))
        elif len(args) == 2:
            one_raw = int(args[1])
            if one_raw % mul != 0:
                raise ValueError("token tampered")
            ids = [one_raw // mul]
        else:
            raise ValueError("bad args len")
    except Exception as e:
        log.exception("id derive failed: %s", e)
        return await message.reply_text("Invalid or expired link.")

    temp = await message.reply("Please wait...")
    try:
        messages = await get_messages(client, ids)
    except Exception as e:
        await temp.delete()
        log.exception("get_messages failed: %s", e)
        return await message.reply_text("Something went wrong..!")
    await temp.delete()

    sent = []
    for msg in messages:
        if not (msg.video or msg.document):
            continue

        caption = msg.caption.html if msg.caption else ""
        if CUSTOM_CAPTION and msg.document:
            try:
                caption = CUSTOM_CAPTION.format(previouscaption=caption, filename=msg.document.file_name)
            except Exception as e:
                log.warning("caption format fail: %s", e)

        reply_markup = None if DISABLE_CHANNEL_BUTTON else msg.reply_markup

        try:
            out = await msg.copy(
                chat_id=uid,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                protect_content=PROTECT_CONTENT
            )
            sent.append(out)
        except FloodWait as e:
            await asyncio.sleep(e.x)
            out = await msg.copy(
                chat_id=uid,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                protect_content=PROTECT_CONTENT
            )
            sent.append(out)
        except Exception as e:
            log.warning("copy failed: %s", e)

    if not sent:
        return await message.reply_text("No video/document found for this link.")

    notice = await client.send_message(
        chat_id=uid,
        text=(f"<b>❗️ <u>IMPORTANT</u> ❗️</b>\n\nThis Video / File Will Be Deleted In {file_auto_delete} "
              f"(Due To Copyright Issues).\n\n📌 Please Forward This Video / File To Somewhere Else And "
              f"Start Downloading There.")
    )
    asyncio.create_task(delete_files(sent, client, notice))


# ------- file delete -------
async def delete_files(messages, client, k):
    await asyncio.sleep(FILE_AUTO_DELETE)
    for msg in messages:
        try:
            await client.delete_messages(chat_id=msg.chat.id, message_ids=[msg.id])
        except Exception as e:
            log.warning("delete %s failed: %s", msg.id, e)
    await k.edit_text("Your Video / File Is Successfully Deleted")
