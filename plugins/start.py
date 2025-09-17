import asyncio, humanize, logging
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

    # Deep-link decode
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
            s_raw = int(args[1])
            e_raw = int(args[2])  # fixed index
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
        # allow only video or document
        if not (msg.video or msg.document):
            # optionally notify user once
            # await client.send_message(uid, "Only video/document supported for this link.")
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

@Bot.on_message(filters.command('start') & filters.private)
async def not_joined(client: Client, message: Message):
    payload = get_payload(message.text) or ""
    buttons = [[InlineKeyboardButton(text="Join Channel", url=client.invitelink)],
               [InlineKeyboardButton(text='Try Again', url=f"https://t.me/{client.username}?start={payload}")]]
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

@Bot.on_message(filters.command('users') & filters.private & filters.user(ADMINS))
async def get_users(client: Bot, message: Message):
    msg = await client.send_message(chat_id=message.chat.id, text="Processing...")
    users = await full_userbase()
    await msg.edit(f"{len(users)} Users Are Using This Bot")

@Bot.on_message(filters.private & filters.command('broadcast') & filters.user(ADMINS))
async def send_text(client: Bot, message: Message):
    if not message.reply_to_message:
        msg = await message.reply("Use this command as a reply to any Telegram message without any spaces.")
        await asyncio.sleep(8)
        return await msg.delete()

    query = await full_userbase()
    broadcast_msg = message.reply_to_message
    total = successful = blocked = deleted = unsuccessful = 0
    pls_wait = await message.reply("<i>Broadcasting Message.. This will take some time</i>")

    for chat_id in query:
        try:
            await broadcast_msg.copy(chat_id)
            successful += 1
        except FloodWait as e:
            await asyncio.sleep(e.x)
            await broadcast_msg.copy(chat_id)
            successful += 1
        except UserIsBlocked:
            await del_user(chat_id)
            blocked += 1
        except InputUserDeactivated:
            await del_user(chat_id)
            deleted += 1
        except Exception:
            unsuccessful += 1
        total += 1

    status = (
        f"<b><u>Broadcast Completed</u></b>\n\n"
        f"<b>Total Users :</b> <code>{total}</code>\n"
        f"<b>Successful :</b> <code>{successful}</code>\n"
        f"<b>Blocked Users :</b> <code>{blocked}</code>\n"
        f"<b>Deleted Accounts :</b> <code>{deleted}</code>\n"
        f"<b>Unsuccessful :</b> <code>{unsuccessful}</code>"
    )
    return await pls_wait.edit(status)

# ------- callbacks (optional) -------
@Bot.on_callback_query(filters.regex("^about$"))
async def about_cb(client: Client, cq: CallbackQuery):
    text = (
        "🤖 My Name : File Sharing Bot\n"
        "💻 Language : Python 3\n"
        "📚 Library : Pyrogram 2.x\n"
        "🗄️ Server : Termux\n"
        "📣 Channel : @YourChannel\n"
        "👨‍💻 Developer : @YourUsername"
    )
    await cq.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔒 Close", callback_data="close"),
              InlineKeyboardButton("◀️ Back", callback_data="back_start")]]
        ),
        disable_web_page_preview=True
    )

@Bot.on_callback_query(filters.regex("^close$"))
async def close_cb(client: Client, cq: CallbackQuery):
    await cq.message.delete()

@Bot.on_callback_query(filters.regex("^back_start$"))
async def back_start_cb(client: Client, cq: CallbackQuery):
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("😊 About Me", callback_data="about"),
          InlineKeyboardButton("🔒 Close", callback_data="close")]]
    )
    m = cq.message
    await m.edit_text(
        START_MSG.format(
            first=m.chat.first_name,
            last=getattr(m.chat, "last_name", None),
            username=None if not m.chat.username else '@' + m.chat.username,
            mention=m.chat.mention,
            id=m.chat.id
        ),
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

# ------- deletions -------
async def delete_files(messages, client, k):
    await asyncio.sleep(FILE_AUTO_DELETE)
    for msg in messages:
        try:
            await client.delete_messages(chat_id=msg.chat.id, message_ids=[msg.id])
        except Exception as e:
            log.warning("delete %s failed: %s", msg.id, e)
    await k.edit_text("Your Video / File Is Successfully Deleted")
