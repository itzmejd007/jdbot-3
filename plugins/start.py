import os
import sys
import random
import logging
import asyncio
import subprocess
from bot import Bot
from datetime import datetime, timedelta
from database.database import kingdb
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from plugins.FORMATS import START_MSG, FORCE_MSG
from pyrogram.enums import ParseMode, ChatAction
from config import CUSTOM_CAPTION, OWNER_ID, PICS
from plugins.autoDelete import auto_del_notification, delete_message
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from helper_func import (
    banUser, is_userJoin, is_admin, subscribed, encode, decode,
    get_messages, generate_hash, get_shortlink
)

# Import premium system
from plugins.prem import PremiumManager

# ==================== Configuration ====================
class Config:
    VERIFICATION_MODE = "off"  # Options: "24" (token), "link" (shortlink), "off" (disabled)
    TOKEN_TIME = 3600  # Access duration in seconds (default: 1 hour)

# ==================== Cache Management ====================
chat_data_cache = {}

# ==================== Helper Classes ====================

class AccessManager:
    """Manages user access, premium status, and session validation"""

    @staticmethod
    async def check_session_validity(user_id: int) -> tuple[bool, datetime]:
        """Check if user's session is still valid"""
        expiry_time = await kingdb.get_variable(f"session_expiry_{user_id}")

        if not expiry_time:
            return False, datetime.min

        # Convert to datetime if it's stored as string
        if isinstance(expiry_time, str):
            try:
                expiry_time = datetime.fromisoformat(expiry_time)
            except:
                return False, datetime.min

        is_valid = expiry_time > datetime.now()
        return is_valid, expiry_time

    @staticmethod
    async def is_premium_user(user_id: int) -> bool:
        """Check if user has premium access using the new PremiumManager"""
        try:
            status = await PremiumManager.check_premium(user_id)
            return status.get("is_premium", False)
        except Exception as e:
            print(f"Error checking premium status: {e}")
            return False

    @staticmethod
    async def grant_temporary_access(user_id: int, duration_seconds: int) -> datetime:
        """Grant temporary access to user"""
        expiry_time = datetime.now() + timedelta(seconds=duration_seconds)
        await kingdb.set_variable(f"session_expiry_{user_id}", expiry_time.isoformat())
        return expiry_time

    @staticmethod
    def format_time_duration(seconds: int) -> str:
        """Convert seconds to human-readable format"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        parts = []
        if hours:
            parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
        if minutes:
            parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
        if secs and not hours:
            parts.append(f"{secs} second{'s' if secs > 1 else ''}")

        return " ".join(parts) if parts else "0 seconds"


class TokenManager:
    """Handles token generation and verification"""

    @staticmethod
    async def generate_verification_token(user_id: int) -> str:
        """Generate and store a verification token for user"""
        token = f"time_{generate_hash()}"
        await kingdb.set_variable(f"verify_token_{user_id}", token)
        return token

    @staticmethod
    async def verify_token(user_id: int, provided_token: str) -> bool:
        """Verify if provided token matches stored token"""
        stored_token = await kingdb.get_variable(f"verify_token_{user_id}")
        return stored_token == provided_token if stored_token else False

    @staticmethod
    async def invalidate_token(user_id: int):
        """Clear user's verification token"""
        await kingdb.set_variable(f"verify_token_{user_id}", None)


class ShortlinkManager:
    """Manages shortlink generation"""

    @staticmethod
    async def create_shortlink(original_url: str) -> str:
        """Create a shortlink for the given URL"""
        try:
            short_url = await get_shortlink(original_url)
            return short_url if short_url else original_url
        except Exception as e:
            print(f"Shortlink generation failed: {e}")
            return original_url


class MessageBuilder:
    """Builds formatted messages and keyboards"""

    @staticmethod
    def build_session_expired_message(duration_str: str) -> str:
        """Build session expired message"""
        return (
            f"<blockquote expandable>⚠️ 𝙎𝙚𝙨𝙨𝙞𝙤𝙣 𝙀𝙭𝙥𝙞𝙧𝙚𝙙 ⚠️</blockquote>\n"
            f"<blockquote expandable>⏳ 𝘼𝙘𝙘𝙚𝙨𝙨 𝙏𝙞𝙢𝙚: {duration_str}</blockquote>\n"
            f"<blockquote expandable>🌟 𝙒𝙝𝙖𝙩'𝙨 𝙩𝙝𝙞𝙨 𝙩𝙤𝙠𝙚𝙣?\n"
            f"🔑 𝙄𝙩'𝙨 𝙖𝙣 𝙖𝙘𝙘𝙚𝙨𝙨 𝙥𝙖𝙨𝙨! 𝙒𝙖𝙩𝙘𝙝 𝙟𝙪𝙨𝙩 1 𝙖𝙙 𝙩𝙤 𝙪𝙣𝙡𝙤𝙘𝙠 "
            f"𝙩𝙝𝙚 𝙗𝙤𝙩 𝙛𝙤𝙧 𝙩𝙝𝙚 𝙣𝙚𝙭𝙩 {duration_str}</blockquote>"
        )

    @staticmethod
    def build_verification_keyboard(link: str) -> InlineKeyboardMarkup:
        """Build keyboard for verification"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 𝐆𝐄𝐓 𝐀𝐂𝐂𝐄𝐒𝐒 🚀", url=link)],
            [InlineKeyboardButton("💎 𝙶𝙴𝚃 𝙿𝚁𝙴𝙼𝙸𝚄𝙼 ", callback_data="prem")]
        ])

    @staticmethod
    def build_download_keyboard(link: str, show_close: bool = True, is_premium: bool = False) -> InlineKeyboardMarkup:
        """Build keyboard for download"""
        buttons = [[InlineKeyboardButton("🚀 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃 🚀", url=link)]]

        if show_close:
            if is_premium:
                # Premium users don't see "Get Premium" button
                buttons.append([InlineKeyboardButton("❌ 𝙲𝙻𝙾𝚂𝙴", callback_data="close")])
            else:
                buttons.append([
                    InlineKeyboardButton("💎 𝙿𝚁𝙴𝙼𝙸𝚄𝙼 ", callback_data="prem"),
                    InlineKeyboardButton("❌ 𝙲𝙻𝙾𝚂𝙴", callback_data="close")
                ])

        return InlineKeyboardMarkup(buttons)


class FileRequestHandler:
    """Handles file/message ID parsing and retrieval"""

    @staticmethod
    def parse_message_ids(argument: list, db_channel_id: int, link_mode: bool = False) -> list:
        """
        Parse message IDs from arguments.

        Supports payloads like:
         - ["get", "<msgid>"]
         - ["get", "<start>", "<end>"]
         - ["set", "<channel_id>", "<msgid>"]
         - ["set", "<channel_id>", "<start>", "<end>"]
         - fallback: find any integers in tokens
        Returns list of message ids or None on failure.
        """
        try:
            tokens = [str(x) for x in (argument or [])]

            def to_int(x):
                return int(x)

            # Case: explicit "set" (set, channel, msgid[,end])
            if tokens and tokens[0].lower() == "set":
                if len(tokens) >= 4:
                    start = to_int(tokens[2])
                    end = to_int(tokens[3])
                    return list(range(start, end + 1)) if start <= end else list(range(start, end - 1, -1))
                if len(tokens) >= 3:
                    return [to_int(tokens[2])]
                return None

            # Case: explicit "get" (get, msgid[,end])
            if tokens and tokens[0].lower() == "get":
                if len(tokens) >= 3:
                    start = to_int(tokens[1])
                    end = to_int(tokens[2])
                    return list(range(start, end + 1)) if start <= end else list(range(start, end - 1, -1))
                if len(tokens) >= 2:
                    return [to_int(tokens[1])]
                return None

            # If link_mode, try to extract any integers from tokens
            if link_mode:
                ints = []
                for t in tokens:
                    try:
                        ints.append(int(t))
                    except Exception:
                        continue
                if not ints:
                    return None
                if len(ints) == 1:
                    return [ints[0]]
                return list(range(ints[0], ints[1] + 1)) if ints[0] <= ints[1] else list(range(ints[0], ints[1] - 1, -1))

            # Fallback: common case where argument is like ["something", "<msgid>"]
            if len(tokens) >= 2:
                return [to_int(tokens[1])]

        except (ValueError, IndexError, ZeroDivisionError):
            pass

        return None


# ==================== Main Command Handlers ====================

@Bot.on_message(filters.command('start') & filters.private & ~banUser & subscribed)
async def start_command(client: Client, message: Message):
    """Main start command handler with premium and shortener management"""
    await message.reply_chat_action(ChatAction.CHOOSE_STICKER)
    user_id = message.from_user.id

    # Initialize user in database
    if not await kingdb.present_user(user_id):
        try:
            await kingdb.add_user(user_id)
        except:
            pass

    text = message.text

    # Handle simple /start command (welcome message)
    if len(text) <= 7:
        await send_welcome_message(client, message)
        return

    # Extract base64 string
    try:
        base64_string = text.split(" ", 1)[1]
    except IndexError:
        return

    # Handle token verification
    if base64_string.startswith("time_"):
        await handle_token_verification(client, message, user_id, base64_string)
        return

    # Clean up prefixes and decode
    base64_string = base64_string.removeprefix("verify_").removeprefix("time_")

    try:
        decoded_string = await decode(base64_string)
        argument = decoded_string.split("-")
    except Exception:
        await message.reply_text("❌ <b>Invalid link format.</b>")
        return

    # Get verification mode from database
    mode = await kingdb.get_variable("mode", "")
    if not mode:
        mode = Config.VERIFICATION_MODE  # Fallback to default

    # Check premium status FIRST using new PremiumManager
    is_premium = await AccessManager.is_premium_user(user_id)

    # Premium users bypass ALL verification
    if is_premium:
        await process_file_request(client, message, user_id, argument, mode == "link", is_premium=True)
        return

    # Skip verification if mode is "off"
    if mode == "off":
        await process_file_request(client, message, user_id, argument)
        return

    # Check session validity for non-premium users
    session_valid, _ = await AccessManager.check_session_validity(user_id)

    # Handle different modes
    if mode == "link" and "set" not in argument:
        # Link mode - Generate shortlink
        await handle_link_mode(client, message, user_id, decoded_string, is_premium)
        return

    # Check if user needs verification (24-hour mode)
    if mode == "24" and not session_valid:
        await handle_session_expired(client, message, user_id)
        return

    # Process the file request
    await process_file_request(client, message, user_id, argument, mode == "link")


async def send_welcome_message(client: Client, message: Message):
    """Send welcome message to user"""
    user_id = message.from_user.id
    
    # Check if user is premium
    is_premium = await AccessManager.is_premium_user(user_id)
    
    # Build buttons
    buttons = [
        [
            InlineKeyboardButton('🤖 Aʙᴏᴜᴛ ᴍᴇ', callback_data='about'),
            InlineKeyboardButton('Sᴇᴛᴛɪɴɢs ⚙️', callback_data='setting')
        ]
    ]
    
    # Add premium status button
    if not is_premium:
        buttons.append([InlineKeyboardButton('💎 Gᴇᴛ Pʀᴇᴍɪᴜᴍ', callback_data='prem')])
    
    reply_markup = InlineKeyboardMarkup(buttons)

    await message.reply_photo(
        photo=random.choice(PICS),
        caption=START_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=None if not message.from_user.username else '@' + message.from_user.username,
            mention=message.from_user.mention,
            id=message.from_user.id
        ),
        reply_markup=reply_markup,
        message_effect_id=5104841245755180586  # 🔥
    )

    try:
        await message.delete()
    except:
        pass


async def handle_token_verification(client: Client, message: Message, user_id: int, token: str):
    """Handle token verification process"""
    if await TokenManager.verify_token(user_id, token):
        # Get token time from database or use default
        token_time = await kingdb.get_variable("token_time") or Config.TOKEN_TIME

        # Grant access
        await AccessManager.grant_temporary_access(user_id, int(token_time))
        await TokenManager.invalidate_token(user_id)

        duration_str = AccessManager.format_time_duration(int(token_time))
        await message.reply_text(
            f"✅ <b>𝐕𝐄𝐑𝐈𝐅𝐈𝐂𝐀𝐓𝐈𝐎𝐍 𝐒𝐔𝐂𝐂𝐄𝐒𝐒𝐅𝐔𝐋</b>\n\n"
            f"🎉 You now have access for the next <b>{duration_str}</b>!\n\n"
            f"💡 <i>Want unlimited access? Get premium!</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Get Premium", callback_data="prem")]
            ])
        )
    else:
        await message.reply_text("❌ <b>Invalid or expired verification token.</b>")


async def handle_session_expired(client: Client, message: Message, user_id: int):
    """Handle expired session by generating verification link"""
    token_time = await kingdb.get_variable("token_time") or Config.TOKEN_TIME
    duration_str = AccessManager.format_time_duration(int(token_time))

    # Generate verification token and link
    token = await TokenManager.generate_verification_token(user_id)
    verification_url = f"https://t.me/{client.me.username}?start={token}"

    # Create shortlink
    short_url = await ShortlinkManager.create_shortlink(verification_url)

    # Build and send message
    message_text = MessageBuilder.build_session_expired_message(duration_str)
    keyboard = MessageBuilder.build_verification_keyboard(short_url)

    await message.reply_text(text=message_text, reply_markup=keyboard)


async def handle_link_mode(client: Client, message: Message, user_id: int, decoded_string: str, is_premium: bool):
    """Handle link mode file sharing"""
    # Prepare the link
    encoded_string = await encode(f"set-{decoded_string}")
    file_url = f"https://t.me/{client.me.username}?start=verify_{encoded_string}"

    # Premium users get direct link
    if is_premium:
        await message.reply_text(
            f"<blockquote expandable>💎 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝘿𝙞𝙧𝙚𝙘𝙩 𝙇𝙞𝙣𝙠</blockquote>\n\n"
            f"<code>{file_url}</code>\n\n"
            f"<i>✨ Tap to copy the link!</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ 𝙲𝙻𝙾𝚂𝙴", callback_data="close")]
            ])
        )
        return

    # Regular users get shortlink
    short_url = await ShortlinkManager.create_shortlink(file_url)

    message_text = "<blockquote expandable>🧩 Here is your download link 👇</blockquote>"
    keyboard = MessageBuilder.build_download_keyboard(short_url, is_premium=False)

    await message.reply_text(text=message_text, reply_markup=keyboard)


async def process_file_request(client: Client, message: Message, user_id: int, argument: list, link_mode: bool = False, is_premium: bool = False):
    """Process and send requested files to user"""
    await message.delete()

    # Parse message IDs
    ids = FileRequestHandler.parse_message_ids(argument, client.db_channel.id, link_mode)

    if not ids:
        await message.reply_text("❌ <b>Invalid file reference.</b>")
        return

    # Fetch messages
    await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)

    try:
        messages = await get_messages(client, ids)
    except Exception as e:
        return await message.reply_text("<b><i>Sᴏᴍᴇᴛʜɪɴɢ ᴡᴇɴᴛ ᴡʀᴏɴɢ..!</i></b>")

    # Get settings from database
    AUTO_DEL, DEL_TIMER, HIDE_CAPTION, CHNL_BTN, PROTECT_MODE = await asyncio.gather(
        kingdb.get_auto_delete(),
        kingdb.get_del_timer(),
        kingdb.get_hide_caption(),
        kingdb.get_channel_button(),
        kingdb.get_protect_content()
    )

    # Premium users don't get auto-delete
    if is_premium:
        AUTO_DEL = False

    if CHNL_BTN:
        button_name, button_link = await kingdb.get_channel_button_link()

    last_message = None

    # Send files
    for idx, msg in enumerate(messages):
        # Handle caption
        if bool(CUSTOM_CAPTION) and bool(msg.document):
            caption = CUSTOM_CAPTION.format(
                previouscaption="" if not msg.caption else msg.caption.html,
                filename=msg.document.file_name
            )
        elif HIDE_CAPTION and (msg.document or msg.audio):
            caption = ""
        else:
            caption = "" if not msg.caption else msg.caption.html

        # Add premium badge to caption if user is premium
        if is_premium and caption:
            caption = f"💎 <b>Premium User</b>\n\n{caption}"

        # Handle reply markup
        if CHNL_BTN:
            reply_markup = (
                InlineKeyboardMarkup([[InlineKeyboardButton(text=button_name, url=button_link)]])
                if msg.document or msg.photo or msg.video or msg.audio
                else None
            )
        else:
            reply_markup = msg.reply_markup

        # Send message
        try:
            copied_msg = await msg.copy(
                chat_id=user_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                protect_content=PROTECT_MODE
            )
            await asyncio.sleep(0.1)

            if AUTO_DEL:
                asyncio.create_task(delete_message(copied_msg, DEL_TIMER))
                if idx == len(messages) - 1:
                    last_message = copied_msg

        except FloodWait as e:
            await asyncio.sleep(e.x)
            copied_msg = await msg.copy(
                chat_id=user_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                protect_content=PROTECT_MODE
            )
            await asyncio.sleep(0.1)

            if AUTO_DEL:
                asyncio.create_task(delete_message(copied_msg, DEL_TIMER))
                if idx == len(messages) - 1:
                    last_message = copied_msg

    # Send auto-delete notification (not for premium users)
    if AUTO_DEL and last_message:
        asyncio.create_task(
            auto_del_notification(client.username, last_message, DEL_TIMER, message.command[1])
        )

# ==================== Force Subscribe Handler ====================

@Bot.on_message(filters.command('start') & filters.private & ~banUser)
async def not_joined(client: Client, message: Message):
    """Handle force subscribe for users who haven't joined required channels"""
    temp = await message.reply("<b>⏳ Checking subscription status...</b>")

    user_id = message.from_user.id
    REQFSUB = await kingdb.get_request_forcesub()

    buttons = []
    count = 0
    total = 0

    try:
        all_channels = await kingdb.get_all_channels()

        for total, chat_id in enumerate(all_channels, start=1):
            await message.reply_chat_action(ChatAction.PLAYING)

            # Check if user has joined this channel
            if not await is_userJoin(client, user_id, chat_id):
                try:
                    # Check cache first
                    if chat_id in chat_data_cache:
                        data = chat_data_cache[chat_id]
                    else:
                        data = await client.get_chat(chat_id)
                        chat_data_cache[chat_id] = data

                    cname = data.title

                    # Handle private channels with request to join
                    if REQFSUB and not data.username:
                        link = await kingdb.get_stored_reqLink(chat_id)
                        await kingdb.add_reqChannel(chat_id)

                        if not link:
                            invite = await client.create_chat_invite_link(
                                chat_id=chat_id,
                                creates_join_request=True
                            )
                            link = invite.invite_link
                            await kingdb.store_reqLink(chat_id, link)
                    else:
                        link = data.invite_link

                    # Add button
                    buttons.append([InlineKeyboardButton(text=cname, url=link)])
                    count += 1
                    await temp.edit(f"<b>{'⏳ ' * min(count, 5)}</b>")

                except Exception as e:
                    print(f"Error fetching channel {chat_id}: {e}")
                    return await temp.edit(
                        f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ</i></b>\n"
                        f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
                    )

        # Add "Try Again" button
        try:
            buttons.append([
                InlineKeyboardButton(
                    text='♻️ Tʀʏ Aɢᴀɪɴ',
                    url=f"https://t.me/{client.me.username}?start={message.command[1]}"
                )
            ])
        except IndexError:
            buttons.append([
                InlineKeyboardButton(
                    text='♻️ Tʀʏ Aɢᴀɪɴ',
                    url=f"https://t.me/{client.me.username}"
                )
            ])

        await message.reply_chat_action(ChatAction.CANCEL)

        # Send force subscribe message
        await temp.edit(
            text=FORCE_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id,
                count=count,
                total=total
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

        try:
            await message.delete()
        except:
            pass

    except Exception as e:
        print(f"Force subscribe error: {e}")
        return await temp.edit(
            f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ</i></b>\n"
            f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
        )


#=====================================================================================##
#......... RESTART COMMAND FOR RESTARTING BOT .......#
#=====================================================================================##

