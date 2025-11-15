from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
import os
import sys

from argon.prem import short, short2, short3, short4
from plugins.prem import prem
from helper_func import is_admin
from config import LOGGER



@Client.on_message(filters.private & filters.command("shortner"))
async def hshort(client, message):
    await short(client, message)


@Client.on_callback_query()
async def global_callback_handler(client, callback_query):
    data = callback_query.data
    if data.startswith("short_"):
        if data != "short_rem":
            await short2(client, callback_query)
        else:
            await short3(client, callback_query)
    elif data.startswith("mode_"):
        await short4(client, callback_query)
    elif data.startswith("prem"):
        await prem(client, callback_query)

    else:
        callback_query.continue_propagation()

@Client.on_message(filters.private & filters.command("restart") & is_admin)
async def restart(client, message):
    await message.reply_text(
        "🔄 <b>Rᴇsᴛᴀʀᴛɪɴɢ ʙᴏᴛ..... by. pro</b>",
        parse_mode=ParseMode.HTML,
    )

    try:
        exit_code = os.system("python3 update.py")

        if exit_code == 0:
            await message.reply_text("✅ Update successful! Restarting bot...")
        else:
            await message.reply_text("⚠️ Update failed! Restarting bot anyway...")

        # Restart the bot process
        os.execv(sys.executable, ["python3", "main.py"])
    except Exception as e:
        print(f"ERROR:-{str(e)}")

@Client.on_message(filters.private & filters.command("log"))
async def send_logs(client, message):
    log_file = "logs.txt"
    await message.reply_text("hi9")
    try:
        if os.path.exists("logs.txt"):
            with open("logs.txt", "rb") as f:
                await message.reply_document(f, caption="📄 Here are the latest logs.")
        else:
            await message.reply_text("⚠️ No logs found.")
    except Exception as e:
        await message.reply_text(f"❌ Failed to send logs: {e}")