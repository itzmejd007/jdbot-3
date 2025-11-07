from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from argon.prem import short, short2, short3, short4



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

    else:
        callback_query.continue_propagation()
