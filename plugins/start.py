import asyncio, humanize, logging, time
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from bot import Bot, tokens, is_token_valid, renew_token
from config import ADMINS, FORCE_MSG, START_MSG, CUSTOM_CAPTION, DISABLE_CHANNEL_BUTTON, PROTECT_CONTENT, FILE_AUTO_DELETE
from helper_func import subscribed, decode, get_messages
from database.database import add_user, del_user, full_userbase, present_user

log = logging.getLogger("start")
file_auto_delete = humanize.naturaldelta(FILE_AUTO_DELETE)

# ----- TOKEN CHECK -----
async def check_token(client: Bot, message: Message):
    user_id = message.from_user.id
    if not is_token_valid(user_id):
        ad_link = "https://example.com/watch-ad"  # change to your real ad link
        text = (
            "🎯 <b>Access Token Required</b>\n\n"
            "आपका टोकन expire हो चुका है या अभी बना नहीं है।\n\n"
            "👇 नीचे दिए लिंक पर क्लिक करें और Ad देखें ताकि नया टोकन मिले:\n\n"
            f"<a href='{ad_link}'>🎬 Watch Ad & Unlock Access</a>\n\n"
            "🕒 टोकन valid रहेगा <b>2 मिनट</b> तक।\n"
            "✅ Ad देखने के बाद <b>/verify</b> टाइप करें।"
        )
        await message.reply_text(text, disable_web_page_preview=False)
        return False
    return True

def get_payload(text: str):
    parts = text.split(maxsplit=1)
    return parts[1] if len(parts) == 2 else None

@Bot.on_message(filters.command("verify") & filters.private)
async def verify_token(_, message):
    user_id = message.from_user.id
    renew_token(user_id, 2)
    await message.reply_text("✅ <b>Token Activated!</b>\nअब आप बॉट से content प्राप्त कर सकते हैं।")

@Bot.on_message(filters.command("start") & filters.private & subscribed)
async def start_command(client: Client, message: Message):
    uid = message.from_user.id
    if not await present_user(uid):
        try:
            await add_user(uid)
        except Exception as e:
            log.warning("add_user failed: %s", e)

    # --- token validation first ---
    if not await check_token(client, message):
        return

    # ---- normal flow if token valid ----
    payload = get_payload(message.text)
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

    # --- deep link decode (same as before) ---
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
            s_raw = int(args[1]); e_raw = int(args[2])
            if s_raw % mul != 0 or e_raw % mul != 0:
                raise ValueError("token tampered")
            start = s_raw // mul; end = e_raw // mul
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
            out = await msg.copy(chat_id=uid, caption=caption, parse_mode=ParseMode.HTML,
                                 reply_markup=reply_markup, protect_content=PROTECT_CONTENT)
            sent.append(out)
        except FloodWait as e:
            await asyncio.sleep(e.x)
            out = await msg.copy(chat_id=uid, caption=caption, parse_mode=ParseMode.HTML,
                                 reply_markup=reply_markup, protect_content=PROTECT_CONTENT)
            sent.append(out)
        except Exception as e:
            log.warning("copy failed: %s", e)

    if not sent:
        return await message.reply_text("No video/document found for this link.")
    notice = await client.send_message(
        chat_id=uid,
        text=(f"<b>❗️ <u>IMPORTANT</u> ❗️</b>\n\nThis Video / File Will Be Deleted In {file_auto_delete}. "
              f"Please forward it somewhere else to keep it safe.")
    )
    asyncio.create_task(delete_files(sent, client, notice))

# ---- same callbacks and delete_files() below (unchanged) ----
