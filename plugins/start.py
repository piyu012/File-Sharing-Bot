import asyncio, humanize, logging, os, json, time
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, WebAppInfo
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from bot import Bot, TOKENS  # import token map
from config import ADMINS, FORCE_MSG, START_MSG, CUSTOM_CAPTION, DISABLE_CHANNEL_BUTTON, PROTECT_CONTENT, FILE_AUTO_DELETE
from helper_func import subscribed, decode, get_messages
from database.database import add_user, del_user, full_userbase, present_user

log = logging.getLogger("start")
file_auto_delete = humanize.naturaldelta(FILE_AUTO_DELETE)
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-render-app.onrender.com/static/index.html")

def renew_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Renew Access Token", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("Try Again", callback_data="try_again")]
    ])  # [web:32]

def has_valid_token(uid: int) -> bool:
    return TOKENS.get(uid, 0) > time.time()  # [web:18]

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
    if not payload:
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("😊 About Me", callback_data="about"),
              InlineKeyboardButton("🔒 Close", callback_data="close")]]
        )
        await message.reply_text(
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
        # show renew panel too
        renew_text = (
            "Your Access Token has expired. Please renew it and try again.

"
            "Token Validity: 24 hours

"
            "Complete one ad to unlock sharable links for 24 hours."
        )
        return await message.reply_text(renew_text, reply_markup=renew_kb())  # [web:32]

    # Gate: require valid token before letting user fetch files
    if not has_valid_token(uid):
        return await message.reply_text(
            "⛔ Access Token expired or missing. Tap Renew Access Token.",
            reply_markup=renew_kb()
        )  # [web:18]

    # Payload decode and fetch
    try:
        decoded = await decode(payload)  # "get-<mulstart>-<mulend>" or "get-<mulid>"
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
        text=(f"<b>❗️ <u>IMPORTANT</u> ❗️</b>

This Video / File Will Be Deleted In {file_auto_delete} "
              f"(Due To Copyright Issues).

📌 Please Forward This Video / File To Somewhere Else And "
              f"Start Downloading There.")
    )
    asyncio.create_task(delete_files(sent, client, notice))

# Force-sub not joined view remains same (optionally add Renew button)
@Bot.on_message(filters.command('start') & filters.private & ~subscribed)
async def not_joined(client: Client, message: Message):
    payload = (message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1)) == 2 else "")
    buttons = [
        [InlineKeyboardButton(text="Join Channel", url=client.invitelink)],
        [InlineKeyboardButton(text='Try Again', url=f"https://t.me/{client.username}?start={payload}")],
        [InlineKeyboardButton(text="Renew Access Token", web_app=WebAppInfo(url=WEBAPP_URL))]
    ]
    await message.reply(
        text=FORCE_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=None if not message.from_user.username else '@' + message.from_user.username,
            mention=message.from_user.mention,
            id=message.from_user.id
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True,
        disable_web_page_preview=True
    )

# ... rest (users/broadcast/about/close/back_start/delete_files) keep as-is ...
