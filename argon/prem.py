import re
import asyncio
from typing import Optional, List
from urllib.parse import urlparse
from dataclasses import dataclass
from helper_func import check_admin

from pyrogram.errors.pyromod.listener_timeout import ListenerTimeout
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Message,
    CallbackQuery,
)

from database.database import kingdb

# Helper functions for database access
async def get_variable(key: str, default=None):
    """Get variable from database"""
    return await kingdb.get_variable(key, default)

async def set_variable(key: str, value):
    """Set variable in database"""
    await kingdb.set_variable(key, value)


@dataclass
class ShortenerConfig:
    """Configuration data class for shortener settings"""
    api: str = "None"
    bypass_count: str = "0"
    website: str = "None"
    short_enabled: Optional[bool] = None
    mode: str = "I"
    token_time: int = 0


class TimeFormatter:
    """Utility class for time formatting"""

    @staticmethod
    def format_seconds(total_seconds: int) -> str:
        """Convert seconds to human-readable format"""
        if total_seconds == 0:
            return "0 seconds"

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        parts = []
        if hours:
            parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
        if minutes:
            parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
        if seconds and not hours:
            parts.append(f"{seconds} second{'s' if seconds > 1 else ''}")

        return " ".join(parts)

    @staticmethod
    def parse_time_string(time_str: str) -> Optional[int]:
        """Parse time string (e.g., '1h', '30m', '45s') to seconds"""
        time_pattern = re.match(r"^(\d+)([hms])$", time_str.lower())

        if not time_pattern:
            return None

        value = int(time_pattern.group(1))
        unit = time_pattern.group(2)

        conversions = {'h': 3600, 'm': 60, 's': 1}
        return value * conversions[unit]


class URLValidator:
    """Utility class for URL validation"""

    @staticmethod
    def is_valid_website_url(url: str) -> bool:
        """Validate if URL is a proper website URL (https://domain.com)"""
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme == "https"
                and bool(parsed.netloc)
                and not parsed.path.strip("/")
            )
        except Exception:
            return False


class ShortenerUI:
    """Handles UI generation for shortener settings"""

    PHOTO_URL = "https://i.ibb.co/5xtpFb2T/f4faad6ca1c1.jpg"
    MESSAGE_EFFECT_ID = 5104841245755180586

    @staticmethod
    def get_mode_status(config: ShortenerConfig) -> tuple:
        """Get mode display status and checkmarks"""
        if not config.short_enabled:
            return "❌", "", ""

        if config.mode == "24":
            return "𝟐𝟒𝐇 ✅", "✅", ""
        elif config.mode == "link":
            return "𝐏𝐄𝐑 𝐋𝐈𝐍𝐊 ✅", "", "✅"

        return "", "", ""

    @staticmethod
    def generate_caption(config: ShortenerConfig) -> str:
        """Generate settings caption"""
        mode_display, _, _ = ShortenerUI.get_mode_status(config)
        time_display = TimeFormatter.format_seconds(config.token_time)

        return (
            f"<blockquote expandable>♻️ 𝐒𝐇𝐎𝐑𝐓𝐍𝐄𝐑 𝐒𝐄𝐓𝐓𝐈𝐍𝐆𝐒 💠</blockquote>\n"
            f"<blockquote>💥 𝐒𝐇𝐎𝐑𝐓𝐍𝐄𝐑 𝐌𝐎𝐃𝐄: {mode_display}</blockquote>\n"
            f"<blockquote>⭐ 𝐕𝐄𝐑𝐈𝐅𝐈𝐂𝐀𝐓𝐈𝐎𝐍 𝐓𝐈𝐌𝐄: {time_display}</blockquote>\n"
            f"<blockquote expandable>⚠️ 𝐀𝐏𝐈: {config.api}</blockquote>\n"
            f"<blockquote expandable>🌐 𝐖𝐄𝐁𝐒𝐈𝐓𝐄: {config.website}</blockquote>\n"
            f"<blockquote expandable>𝐋𝐈𝐍𝐊𝐒 𝐁𝐘𝐏𝐀𝐒𝐒𝐄𝐃: {config.bypass_count}</blockquote>"
        )

    @staticmethod
    def generate_keyboard(config: ShortenerConfig) -> InlineKeyboardMarkup:
        """Generate inline keyboard"""
        _, mode_24_check, mode_link_check = ShortenerUI.get_mode_status(config)

        return InlineKeyboardMarkup([
            [InlineKeyboardButton("𝐑𝐄𝐌𝐎𝐕𝐄 𝐒𝐇𝐎𝐑𝐓𝐄𝐑 ❌", callback_data="short_rem")],
            [
                InlineKeyboardButton(f"𝟐𝟒𝐇 𝐌𝐎𝐃𝐄 {mode_24_check}", callback_data="mode_24"),
                InlineKeyboardButton(f"𝐏𝐄𝐑 𝐋𝐈𝐍𝐊 𝐌𝐎𝐃𝐄 {mode_link_check}", callback_data="mode_link"),
            ],
            [
                InlineKeyboardButton("𝐂𝐇𝐀𝐍𝐆𝐄 𝐖𝐄𝐁𝐒𝐈𝐓𝐄", callback_data="short_web"),
                InlineKeyboardButton("𝐂𝐇𝐀𝐍𝐆𝐄 𝐀𝐏𝐈", callback_data="short_api"),
            ],
            [InlineKeyboardButton("𝐂𝐋𝐎𝐒𝐄", callback_data="close")],
        ])


class AdminChecker:
    """Handles admin authorization"""

    @staticmethod
    async def get_admin_list() -> List[int]:
        """Retrieve and parse admin list"""
        admin_str = await get_variable(
            "owner",
            "-1002374561133 -1002252580234 -1002359972599 5426061889"
        )
        return [int(x.strip()) for x in admin_str.split()]

    @staticmethod
    async def is_admin(user_id: int) -> bool:
        """Check if user is admin"""
        return await check_admin(None, None, None, user_id=user_id)


class ShortenerManager:
    """Main shortener management class"""

    TIMEOUT = 30

    @staticmethod
    async def load_config() -> ShortenerConfig:
        """Load current shortener configuration"""
        return ShortenerConfig(
            api=await get_variable("api", "None"),
            bypass_count=await get_variable("bypass", "0"),
            website=await get_variable("website", "None"),
            short_enabled=await get_variable("short", None),
            mode=await get_variable("mode", "I"),
            token_time=int(await get_variable("token_time", 0))
        )

    @staticmethod
    async def send_settings(client, message: Message):
        """Display shortener settings"""
        config = await ShortenerManager.load_config()
        caption = ShortenerUI.generate_caption(config)
        keyboard = ShortenerUI.generate_keyboard(config)

        await message.reply_photo(
            photo=ShortenerUI.PHOTO_URL,
            caption=caption,
            reply_markup=keyboard,
            message_effect_id=ShortenerUI.MESSAGE_EFFECT_ID,
        )

    @staticmethod
    async def refresh_settings(client, message: Message):
        """Refresh settings display after changes"""
        try:
            await message.delete()
        except Exception:
            pass
        await ShortenerManager.send_settings(client, message)

    @staticmethod
    async def request_user_input(
        client,
        user_id: int,
        prompt: str,
        validator=None
    ) -> Optional[str]:
        """
        Generic method to request and validate user input

        Args:
            client: Pyrogram client
            user_id: User ID to listen to
            prompt: Prompt message to display
            validator: Optional validation function

        Returns:
            User input if valid, None if cancelled or timeout
        """
        prompt_msg = await client.send_message(
            user_id,
            text=prompt,
            reply_markup=ReplyKeyboardMarkup(
                [["❌ Cancel"]],
                one_time_keyboard=True,
                resize_keyboard=True
            ),
        )

        try:
            while True:
                try:
                    response = await client.listen(
                        user_id=user_id,
                        timeout=ShortenerManager.TIMEOUT,
                        chat_id=user_id
                    )
                except ListenerTimeout:
                    await client.send_message(
                        chat_id=user_id,
                        text="⏳ 𝐓𝐢𝐦𝐞𝐨𝐮𝐭! 𝐒𝐞𝐭𝐮𝐩 𝐜𝐚𝐧𝐜𝐞𝐥𝐥𝐞𝐝.",
                        reply_markup=ReplyKeyboardRemove(),
                    )
                    return None

                if response.text.lower() == "❌ cancel":
                    await client.send_message(
                        chat_id=user_id,
                        text="❌ 𝐒𝐞𝐭𝐮𝐩 𝐜𝐚𝐧𝐜𝐞𝐥𝐥𝐞𝐝.",
                        reply_markup=ReplyKeyboardRemove(),
                    )
                    return None

                # If no validator, return input directly
                if validator is None:
                    return response.text

                # Validate input
                is_valid, error_msg = validator(response.text)
                if is_valid:
                    return response.text

                # Show error and retry
                await client.send_message(
                    chat_id=user_id,
                    text=error_msg,
                    reply_markup=ReplyKeyboardRemove(),
                )
        finally:
            try:
                await prompt_msg.delete()
            except Exception:
                pass


# Handler Functions

async def short(client, message: Message):
    """Display shortener settings"""
    await ShortenerManager.send_settings(client, message)


async def short2(client, query: CallbackQuery):
    """Handle website and API configuration"""
    if not await AdminChecker.is_admin(query.from_user.id):
        await query.answer(
            "❌ 𝐘𝐨𝐮 𝐚𝐫𝐞 𝐧𝐨𝐭 𝐚𝐮𝐭𝐡𝐨𝐫𝐢𝐳𝐞𝐝 𝐭𝐨 𝐮𝐬𝐞 𝐭𝐡𝐢𝐬 𝐛𝐮𝐭𝐭𝐨𝐧!",
            show_alert=True
        )
        return

    action = query.data.split("_")[1]
    user_id = query.from_user.id

    if action == "web":
        # Website configuration
        def validate_website(url: str) -> tuple:
            if URLValidator.is_valid_website_url(url):
                return True, None
            return False, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐔𝐑𝐋! 𝐏𝐥𝐞𝐚𝐬𝐞 𝐬𝐞𝐧𝐝 𝐚 𝐯𝐚𝐥𝐢𝐝 𝐔𝐑𝐋 𝐥𝐢𝐤𝐞: https://example.com"

        website = await ShortenerManager.request_user_input(
            client,
            user_id,
            "<blockquote expandable>𝐏𝐋𝐄𝐀𝐒𝐄 𝐒𝐄𝐍𝐃 𝐒𝐇𝐎𝐑𝐓𝐍𝐄𝐑 𝐖𝐄𝐁𝐒𝐈𝐓𝐄\n"
            "𝐅𝐨𝐫𝐦𝐚𝐭: https://example.com</blockquote>",
            validate_website
        )

        if website:
            await set_variable("website", website)
            await client.send_message(
                chat_id=user_id,
                text="✅ 𝐖𝐄𝐁𝐒𝐈𝐓𝐄 𝐀𝐃𝐃𝐄𝐃 𝐒𝐔𝐂𝐂𝐄𝐒𝐒𝐅𝐔𝐋𝐋𝐘!",
                reply_markup=ReplyKeyboardRemove(),
            )
            await ShortenerManager.refresh_settings(client, query.message)

    elif action == "api":
        # API configuration
        api_key = await ShortenerManager.request_user_input(
            client,
            user_id,
            "<blockquote expandable>𝐏𝐋𝐄𝐀𝐒𝐄 𝐒𝐄𝐍𝐃 𝐒𝐇𝐎𝐑𝐓𝐍𝐄𝐑 𝐀𝐏𝐈 𝐊𝐄𝐘</blockquote>"
        )

        if api_key:
            await set_variable("api", api_key)
            await client.send_message(
                chat_id=user_id,
                text="✅ 𝐀𝐏𝐈 𝐀𝐃𝐃𝐄𝐃 𝐒𝐔𝐂𝐂𝐄𝐒𝐒𝐅𝐔𝐋𝐋𝐘!",
                reply_markup=ReplyKeyboardRemove(),
            )
            await ShortenerManager.refresh_settings(client, query.message)


async def short3(client, query: CallbackQuery):
    """Remove shortener configuration"""
    if not await AdminChecker.is_admin(query.from_user.id):
        await query.answer(
            "❌ 𝐘𝐨𝐮 𝐚𝐫𝐞 𝐧𝐨𝐭 𝐚𝐮𝐭𝐡𝐨𝐫𝐢𝐳𝐞𝐝 𝐭𝐨 𝐮𝐬𝐞 𝐭𝐡𝐢𝐬 𝐛𝐮𝐭𝐭𝐨𝐧!",
            show_alert=True
        )
        return

    config = await ShortenerManager.load_config()

    if config.short_enabled:
        await set_variable("short", False)
        await set_variable("mode", None)
        await query.answer("✅ 𝐒𝐡𝐨𝐫𝐭𝐞𝐧𝐞𝐫 𝐫𝐞𝐦𝐨𝐯𝐞𝐝 𝐬𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥𝐥𝐲!", show_alert=True)
        await ShortenerManager.refresh_settings(client, query.message)
    else:
        await query.answer(
            "⚠️ 𝐒𝐡𝐨𝐫𝐭𝐞𝐧𝐞𝐫 𝐢𝐬 𝐚𝐥𝐫𝐞𝐚𝐝𝐲 𝐝𝐢𝐬𝐚𝐛𝐥𝐞𝐝!",
            show_alert=True
        )


async def short4(client, query: CallbackQuery):
    """Handle mode changes (24h or per-link)"""
    if not await AdminChecker.is_admin(query.from_user.id):
        await query.answer(
            "❌ 𝐘𝐨𝐮 𝐚𝐫𝐞 𝐧𝐨𝐭 𝐚𝐮𝐭𝐡𝐨𝐫𝐢𝐳𝐞𝐝 𝐭𝐨 𝐮𝐬𝐞 𝐭𝐡𝐢𝐬 𝐛𝐮𝐭𝐭𝐨𝐧!",
            show_alert=True
        )
        return

    action = query.data.split("_")[1]
    config = await ShortenerManager.load_config()

    if action == "link":
        # Enable per-link mode
        if not config.short_enabled:
            await set_variable("short", True)
        await set_variable("mode", "link")
        await query.answer("✅ 𝐏𝐞𝐫-𝐥𝐢𝐧𝐤 𝐦𝐨𝐝𝐞 𝐞𝐧𝐚𝐛𝐥𝐞𝐝!", show_alert=True)
        await ShortenerManager.refresh_settings(client, query.message)

    elif action == "24":
        # Configure 24h mode with verification time
        def validate_time(time_str: str) -> tuple:
            seconds = TimeFormatter.parse_time_string(time_str)
            if seconds is not None:
                return True, None
            return False, (
                "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐟𝐨𝐫𝐦𝐚𝐭! 𝐔𝐬𝐞: 1h, 30m, 𝐨𝐫 45s"
            )

        try:
            await query.message.edit(
                text=(
                    "⚠️ 𝐒𝐞𝐧𝐝 𝐕𝐄𝐑𝐈𝐅𝐈𝐂𝐀𝐓𝐈𝐎𝐍 𝐓𝐈𝐌𝐄 𝐅𝐨𝐫𝐦𝐚𝐭:\n"
                    "<blockquote>"
                    "• Xh - 𝐟𝐨𝐫 X 𝐡𝐨𝐮𝐫𝐬 (𝐞𝐱: 1h)\n"
                    "• Xm - 𝐟𝐨𝐫 X 𝐦𝐢𝐧𝐮𝐭𝐞𝐬 (𝐞𝐱: 30m)\n"
                    "• Xs - 𝐟𝐨𝐫 X 𝐬𝐞𝐜𝐨𝐧𝐝𝐬 (𝐞𝐱: 45s)"
                    "</blockquote>"
                ),
                reply_markup=ReplyKeyboardMarkup(
                    [["❌ Cancel"]],
                    one_time_keyboard=True,
                    resize_keyboard=True
                ),
            )
        except Exception:
            pass

        time_input = await ShortenerManager.request_user_input(
            client,
            query.from_user.id,
            None,  # Already edited message above
            validate_time
        )

        if time_input:
            seconds = TimeFormatter.parse_time_string(time_input)
            await set_variable("token_time", str(seconds))

            if not config.short_enabled:
                await set_variable("short", True)
            await set_variable("mode", "24")

            await client.send_message(
                chat_id=query.from_user.id,
                text=f"✅ 𝟐𝟒𝐡 𝐦𝐨𝐝𝐞 𝐞𝐧𝐚𝐛𝐥𝐞𝐝!\n⏱️ 𝐕𝐞𝐫𝐢𝐟𝐢𝐜𝐚𝐭𝐢𝐨𝐧 𝐭𝐢𝐦𝐞: {TimeFormatter.format_seconds(seconds)}",
                reply_markup=ReplyKeyboardRemove(),
            )
            await ShortenerManager.refresh_settings(client, query.message)
        else:
            # Restore original message if cancelled
            await ShortenerManager.refresh_settings(client, query.message)