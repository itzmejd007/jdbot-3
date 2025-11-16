import asyncio
from datetime import datetime, timedelta
from bot import Bot
from config import OWNER_ID, LOGGER
from database.database import kingdb
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode, ChatAction
from helper_func import is_admin

logger=LOGGER(__name__)

# ==================== Helper Classes ====================
async def send_premium_tutorial(message: Message, error: str = None) -> None:
    """
    Send premium command usage tutorial
    
    Args:
        message: The message object to reply to
        error: Optional error message to display
    """
    
    error_text = ""
    if error:
        error_text = f"<blockquote expandable>❌ 𝙀𝙧𝙧𝙤𝙧</blockquote>\n\n<b>⚠️ {error}</b>\n\n"
    
    tutorial_text = (
        f"{error_text}"
        f"<blockquote expandable>📚 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝘾𝙤𝙢𝙢𝙖𝙣𝙙 𝙂𝙪𝙞𝙙𝙚</blockquote>\n\n"
        f"<b>🔧 Command Format:</b>\n"
        f"<code>/addpremium [user_id] [duration]</code>\n\n"
        f"<b>⏰ Duration Format:</b>\n"
        f"• <code>30s</code> - 30 seconds\n"
        f"• <code>5m</code> - 5 minutes\n"
        f"• <code>2h</code> - 2 hours\n"
        f"• <code>7d</code> - 7 days\n"
        f"• <code>3w</code> - 3 weeks\n"
        f"• <code>2mo</code> - 2 months\n"
        f"• <code>1y</code> - 1 year\n\n"
        f"<b>💡 Examples:</b>\n"
        f"<code>/addpremium 123456789 1mo</code>\n"
        f"<i>→ Adds 1 month premium</i>\n\n"
        f"<code>/addpremium 987654321 7d</code>\n"
        f"<i>→ Adds 7 days premium</i>\n\n"
        f"<code>/addpremium 555555555 1y</code>\n"
        f"<i>→ Adds 1 year premium</i>\n\n"
        f"<b>📋 Available Time Units:</b>\n"
        f"• <code>s</code> = Seconds\n"
        f"• <code>m</code> = Minutes\n"
        f"• <code>h</code> = Hours\n"
        f"• <code>d</code> = Days\n"
        f"• <code>w</code> = Weeks\n"
        f"• <code>mo</code> = Months\n"
        f"• <code>y</code> = Years\n\n"
        f"<blockquote expandable><i>⚡ Quick Tip: You can combine numbers with units for precise control!</i></blockquote>"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 View Premium Info", callback_data="prem")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])
    
    await message.reply_text(
        tutorial_text,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )
    
  
def parse_duration(duration_str: str) -> int:
    """
    Parse duration string and return seconds
    
    Supports: s (seconds), m (minutes), h (hours), d (days), w (weeks), mo (months), y (years)
    
    Args:
        duration_str: Duration string (e.g., "30d", "2mo", "1y")
    
    Returns:
        int: Duration in seconds, or None if invalid
    """
    import re
    
    # Pattern to match number followed by time unit
    pattern = r'^(\d+)(s|m|h|d|w|mo|y)$'
    match = re.match(pattern, duration_str.lower())
    
    if not match:
        return None
    
    amount = int(match.group(1))
    unit = match.group(2)
    
    # Convert to seconds
    conversions = {
        's': 1,                    # seconds
        'm': 60,                   # minutes
        'h': 3600,                 # hours
        'd': 86400,                # days
        'w': 604800,               # weeks
        'mo': 2592000,             # months (30 days)
        'y': 31536000              # years (365 days)
    }
    
    return amount * conversions.get(unit, 0)


def format_duration_display(seconds: int) -> str:
    """
    Format seconds into human-readable duration
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        str: Formatted duration string
    """
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    elif seconds < 604800:
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''}"
    elif seconds < 2592000:
        weeks = seconds // 604800
        return f"{weeks} week{'s' if weeks != 1 else ''}"
    elif seconds < 31536000:
        months = seconds // 2592000
        return f"{months} month{'s' if months != 1 else ''}"
    else:
        years = seconds // 31536000
        months = (seconds % 31536000) // 2592000
        if months > 0:
            return f"{years} year{'s' if years != 1 else ''} {months} month{'s' if months != 1 else ''}"
        return f"{years} year{'s' if years != 1 else ''}"

class PremiumManager:
    """Centralized premium management system"""

    @staticmethod
    async def add_premium(user_id: int, duration_seconds: int, added_by: int) -> dict:
        """
        Add premium access to a user
        Returns: dict with success status and message
        """
        try:
            expiry_date = datetime.now() + timedelta(seconds=duration_seconds)

            # Store premium data
            await kingdb.set_variable(f"premium_{user_id}", {
                "expiry": expiry_date.isoformat(),
                "added_by": added_by,
                "added_at": datetime.now().isoformat(),
                "duration_seconds": duration_seconds
            })

            return {
                "success": True,
                "expiry_date": expiry_date,
                "message": f"Premium added successfully until {expiry_date.strftime('%d %b %Y, %I:%M %p')}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to add premium: {str(e)}"
            }

    @staticmethod
    async def remove_premium(user_id: int) -> dict:
        """Remove premium access from a user"""
        try:
            premium_data = await kingdb.get_variable(f"premium_{user_id}")

            if not premium_data:
                return {
                    "success": False,
                    "message": "User doesn't have premium access"
                }

            await kingdb.set_variable(f"premium_{user_id}", None)

            return {
                "success": True,
                "message": "Premium access removed successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to remove premium: {str(e)}"
            }

    @staticmethod
    async def check_premium(user_id: int) -> dict:
        """
        Check premium status of a user
        Returns: dict with premium status and details
        """
        try:
            premium_data = await kingdb.get_variable(f"premium_{user_id}")

            if not premium_data:
                return {
                    "is_premium": False,
                    "message": "User doesn't have premium access"
                }

            expiry = datetime.fromisoformat(premium_data["expiry"])
            now = datetime.now()

            if expiry < now:
                # Premium expired
                await PremiumManager.remove_premium(user_id)
                return {
                    "is_premium": False,
                    "expired": True,
                    "message": "Premium access has expired"
                }

            time_left = expiry - now
            days_left = time_left.days
            hours_left = time_left.seconds // 3600

            return {
                "is_premium": True,
                "expiry_date": expiry,
                "days_left": days_left,
                "hours_left": hours_left,
                "added_by": premium_data.get("added_by"),
                "added_at": premium_data.get("added_at"),
                "duration_seconds": premium_data.get("duration_seconds", 0)
            }
        except Exception as e:
            return {
                "is_premium": False,
                "error": True,
                "message": f"Error checking premium: {str(e)}"
            }

    @staticmethod
    async def get_all_premium_users() -> list:
        """Get list of all premium users"""
        try:
            all_users = await kingdb.full_userbase()
            premium_users = []

            for user_id in all_users:
                status = await PremiumManager.check_premium(user_id)
                if status.get("is_premium"):
                    premium_users.append({
                        "user_id": user_id,
                        **status
                    })

            return premium_users
        except Exception as e:
            print(f"Error fetching premium users: {e}")
            return []

    @staticmethod
    def format_time_remaining(days: int, hours: int) -> str:
        """Format remaining time in human-readable format"""
        if days > 0:
            return f"{days} day{'s' if days > 1 else ''} {hours} hour{'s' if hours > 1 else ''}"
        elif hours > 0:
            return f"{hours} hour{'s' if hours > 1 else ''}"
        else:
            return "Less than 1 hour"


# ==================== Message Builders ====================

class PremiumMessageBuilder:
    """Build formatted premium messages"""

    @staticmethod
    def build_add_success_message(user_id: int, expiry_date: datetime, duration_display: str) -> str:
        """Build premium added success message"""
        return (
            f"<blockquote expandable>✅ 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝘼𝙙𝙙𝙚𝙙 𝙎𝙪𝙘𝙘𝙚𝙨𝙨𝙛𝙪𝙡𝙡𝙮</blockquote>\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"⏰ <b>Duration:</b> <code>{duration_display}</code>\n"
            f"📅 <b>Expires On:</b> <code>{expiry_date.strftime('%d %b %Y, %I:%M %p')}</code>\n\n"
            f"💎 <i>User now has premium access with unlimited features!</i>"
        )

    @staticmethod
    def build_remove_success_message(user_id: int) -> str:
        """Build premium removed success message"""
        return (
            f"<blockquote expandable>🗑️ 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙍𝙚𝙢𝙤𝙫𝙚𝙙</blockquote>\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n\n"
            f"ℹ️ <i>Premium access has been revoked</i>"
        )

    @staticmethod
    def build_status_message(user_id: int, status: dict) -> str:
        """Build premium status message"""
        if not status.get("is_premium"):
            return (
                f"<blockquote expandable>❌ 𝙉𝙤 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝘼𝙘𝙘𝙚𝙨𝙨</blockquote>\n\n"
                f"👤 <b>User ID:</b> <code>{user_id}</code>\n\n"
                f"ℹ️ <i>This user doesn't have premium access</i>"
            )

        time_left = PremiumManager.format_time_remaining(
            status["days_left"],
            status["hours_left"]
        )

        added_at = datetime.fromisoformat(status["added_at"]).strftime('%d %b %Y, %I:%M %p')
        expiry = status["expiry_date"].strftime('%d %b %Y, %I:%M %p')
        duration_display = format_duration_display(status["duration_seconds"])

        return (
            f"<blockquote expandable>💎 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙐𝙨𝙚𝙧</blockquote>\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"⏳ <b>Time Left:</b> <code>{time_left}</code>\n"
            f"📅 <b>Expires On:</b> <code>{expiry}</code>\n"
            f"🎁 <b>Added On:</b> <code>{added_at}</code>\n"
            f"👨‍💼 <b>Added By:</b> <code>{status['added_by']}</code>\n"
            f"📊 <b>Total Duration:</b> <code>{duration_display}</code>\n\n"
            f"✨ <i>Enjoying premium features!</i>"
        )

    @staticmethod
    def build_list_message(premium_users: list, page: int = 1, per_page: int = 10) -> tuple:
        """Build premium users list message with pagination"""
        if not premium_users:
            return (
                "<blockquote expandable>📋 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙐𝙨𝙚𝙧𝙨 𝙇𝙞𝙨𝙩</blockquote>\n\n"
                "ℹ️ <i>No premium users found</i>",
                None
            )

        total_users = len(premium_users)
        total_pages = (total_users + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        page_users = premium_users[start_idx:end_idx]

        message = (
            f"<blockquote expandable>📋 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙐𝙨𝙚𝙧𝙨 𝙇𝙞𝙨𝙩</blockquote>\n\n"
            f"📊 <b>Total Premium Users:</b> <code>{total_users}</code>\n"
            f"📄 <b>Page:</b> <code>{page}/{total_pages}</code>\n\n"
        )

        for idx, user in enumerate(page_users, start=start_idx + 1):
            time_left = PremiumManager.format_time_remaining(
                user["days_left"],
                user["hours_left"]
            )
            message += (
                f"<b>{idx}.</b> 👤 <code>{user['user_id']}</code>\n"
                f"   ⏳ <i>{time_left} left</i>\n\n"
            )

        # Build pagination keyboard
        buttons = []
        nav_buttons = []

        if page > 1:
            nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"prem_list_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"prem_list_{page+1}"))

        if nav_buttons:
            buttons.append(nav_buttons)

        buttons.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"prem_list_{page}")])
        buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])

        return message, InlineKeyboardMarkup(buttons)


# ==================== Command Handlers ====================

@Client.on_message(filters.command(['addpremium', 'addprem']) & filters.private)
async def add_premium_command(client: Client, message: Message):
    """Add premium access to a user"""
    await message.reply_chat_action(ChatAction.TYPING)

    # Check if user is admin
    if not await is_admin(0, 0, message.from_user.id):
        return await message.reply_text(
            "<blockquote expandable>⛔ 𝘼𝙘𝙘𝙚𝙨𝙨 𝘿𝙚𝙣𝙞𝙚𝙙</blockquote>\n\n"
            "❌ <i>Only admins can use this command</i>"
        )

    # Parse command arguments
    args = message.text.split()

    if len(args) < 3:
        return await send_premium_tutorial(message)

    try:
        user_id = int(args[1])
        duration_input = args[2].lower()

        # Parse duration with time unit
        duration_seconds = parse_duration(duration_input)

        if duration_seconds is None:
            return await send_premium_tutorial(message, error="Invalid duration format")

        if duration_seconds <= 0:
            return await send_premium_tutorial(message, error="Duration must be greater than 0")

    except ValueError:
        return await send_premium_tutorial(message, error="User ID must be a valid number")

    # Convert seconds to days for storage
    duration_days = duration_seconds / 86400

    # Add premium
    result = await PremiumManager.add_premium(user_id, duration_seconds, message.from_user.id)

    if result["success"]:
        # Format duration for display
        duration_display = format_duration_display(duration_seconds)

        success_msg = PremiumMessageBuilder.build_add_success_message(
            user_id,
            result["expiry_date"],
            duration_display
        )
        await message.reply_text(success_msg)

        # Notify the user
        try:
            await client.send_message(
                chat_id=user_id,
                text=(
                    f"<blockquote expandable>🎉 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝘼𝙘𝙩𝙞𝙫𝙖𝙩𝙚𝙙</blockquote>\n\n"
                    f"💎 <b>Congratulations!</b>\n\n"
                    f"You've been granted <b>{duration_display}</b> of premium access!\n\n"
                    f"📅 <b>Valid Until:</b> <code>{result['expiry_date'].strftime('%d %b %Y, %I:%M %p')}</code>\n\n"
                    f"✨ <b>Premium Benefits:</b>\n"
                    f"• 🚫 No ads or verification\n"
                    f"• ⚡ Direct download links\n"
                    f"• 🎯 Priority support\n"
                    f"• 🔓 Unlimited access\n\n"
                    f"<i>Enjoy your premium experience!</i> 🎊"
                )
            )
        except Exception as e:
            print(f"Failed to notify user {user_id}: {e}")
    else:
        await message.reply_text(
            f"<blockquote expandable>❌ 𝙁𝙖𝙞𝙡𝙚𝙙</blockquote>\n\n"
            f"<b>Error:</b> <code>{result['message']}</code>"
        )


@Client.on_message(filters.command(['removepremium', 'remprem', 'delprem']) & filters.private)
async def remove_premium_command(client: Client, message: Message):
    """Remove premium access from a user"""
    await message.reply_chat_action(ChatAction.TYPING)

    # Check if user is admin
    if not await is_admin(0, 0, message.from_user.id):
        return await message.reply_text(
            "<blockquote expandable>⛔ 𝘼𝙘𝙘𝙚𝙨𝙨 𝘿𝙚𝙣𝙞𝙚𝙙</blockquote>\n\n"
            "❌ <i>Only admins can use this command</i>"
        )

    # Parse command arguments
    try:
        args = message.text.split()
        if len(args) < 2:
            return await message.reply_text(
                "<blockquote expandable>ℹ️ 𝙐𝙨𝙖𝙜𝙚 𝙂𝙪𝙞𝙙𝙚</blockquote>\n\n"
                "<b>Command:</b> <code>/removepremium [user_id]</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/removepremium 123456789</code>"
            )

        user_id = int(args[1])

    except ValueError:
        return await message.reply_text(
            "❌ <b>Invalid format!</b>\n\n"
            "ℹ️ <i>User ID must be a number</i>"
        )

    # Remove premium
    result = await PremiumManager.remove_premium(user_id)

    if result["success"]:
        success_msg = PremiumMessageBuilder.build_remove_success_message(user_id)
        await message.reply_text(success_msg)

        # Notify the user
        try:
            await client.send_message(
                chat_id=user_id,
                text=(
                    f"<blockquote expandable>ℹ️ 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙀𝙭𝙥𝙞𝙧𝙚𝙙</blockquote>\n\n"
                    f"Your premium access has ended.\n\n"
                    f"💡 <i>Contact admin to renew premium access</i>"
                )
            )
        except Exception as e:
            print(f"Failed to notify user {user_id}: {e}")
    else:
        await message.reply_text(
            f"<blockquote expandable>❌ 𝙁𝙖𝙞𝙡𝙚𝙙</blockquote>\n\n"
            f"<b>Error:</b> <code>{result['message']}</code>"
        )


@Client.on_message(filters.command(['checkpremium', 'premstatus']) & filters.private)
async def check_premium_command(client: Client, message: Message):
    """Check premium status of a user"""
    await message.reply_chat_action(ChatAction.TYPING)

    # Parse command arguments
    try:
        args = message.text.split()

        # If no user_id provided, check self
        if len(args) < 2:
            user_id = message.from_user.id
        else:
            # Only admins can check other users
            if not await is_admin(0, 0, message.from_user.id):
                return await message.reply_text(
                    "<blockquote expandable>⛔ 𝘼𝙘𝙘𝙚𝙨𝙨 𝘿𝙚𝙣𝙞𝙚𝙙</blockquote>\n\n"
                    "❌ <i>Only admins can check other users' premium status</i>"
                )
            user_id = int(args[1])

    except ValueError:
        return await message.reply_text(
            "❌ <b>Invalid format!</b>\n\n"
            "ℹ️ <i>User ID must be a number</i>"
        )

    # Check premium status
    status = await PremiumManager.check_premium(user_id)
    status_msg = PremiumMessageBuilder.build_status_message(user_id, status)

    await message.reply_text(status_msg)


@Client.on_message(filters.command(['listpremium', 'premlist', 'premiumusers']) & filters.private)
async def list_premium_command(client: Client, message: Message):
    """List all premium users"""
    await message.reply_chat_action(ChatAction.TYPING)

    # Check if user is admin
    if not await is_admin(0, 0, message.from_user.id):
        return await message.reply_text(
            "<blockquote expandable>⛔ 𝘼𝙘𝙘𝙚𝙨𝙨 𝘿𝙚𝙣𝙞𝙚𝙙</blockquote>\n\n"
            "❌ <i>Only admins can view premium users list</i>"
        )
    try:
        # Get all premium users
        premium_users = await PremiumManager.get_all_premium_users()
    
        # Build and send list
        list_msg, keyboard = PremiumMessageBuilder.build_list_message(premium_users)
        await message.reply_text(list_msg, reply_markup=keyboard)
    except Exception as e:
        logger.error(e)


@Client.on_message(filters.command('mypremium') & filters.private)
async def my_premium_command(client: Client, message: Message):
    """Check own premium status"""
    await message.reply_chat_action(ChatAction.TYPING)

    status = await PremiumManager.check_premium(message.from_user.id)

    if not status.get("is_premium"):
        return await message.reply_text(
            "<blockquote expandable>ℹ️ 𝙉𝙤 𝙋𝙧𝙚𝙢𝙞𝙪𝙢</blockquote>\n\n"
            "You don't have premium access currently.\n\n"
            "💎 <b>Get Premium Benefits:</b>\n"
            "• 🚫 No ads or verification\n"
            "• ⚡ Direct download links\n"
            "• 🎯 Priority support\n"
            "• 🔓 Unlimited access\n\n"
            "💡 <i>Contact admin to get premium!</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💎 Get Premium", callback_data="prem")
            ]])
        )

    time_left = PremiumManager.format_time_remaining(
        status["days_left"],
        status["hours_left"]
    )

    expiry = status["expiry_date"].strftime('%d %b %Y, %I:%M %p')

    await message.reply_text(
        f"<blockquote expandable>💎 𝙔𝙤𝙪𝙧 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙎𝙩𝙖𝙩𝙪𝙨</blockquote>\n\n"
        f"✅ <b>Premium Active</b>\n\n"
        f"⏳ <b>Time Remaining:</b> <code>{time_left}</code>\n"
        f"📅 <b>Valid Until:</b> <code>{expiry}</code>\n\n"
        f"✨ <b>Active Benefits:</b>\n"
        f"• 🚫 No ads or verification\n"
        f"• ⚡ Direct download links\n"
        f"• 🎯 Priority support\n"
        f"• 🔓 Unlimited access\n\n"
        f"<i>Enjoy your premium experience!</i> 🎊"
    )


# ==================== Callback Query Handlers ====================

@Client.on_callback_query(filters.regex(r'^prem_list_(\d+)$'))
async def premium_list_pagination(client: Client, query: CallbackQuery):
    """Handle premium list pagination"""

    # Check if user is admin
    if not await is_admin(query.from_user.id):
        return await query.answer("⛔ Only admins can view this!", show_alert=True)

    page = int(query.data.split('_')[-1])

    # Get all premium users
    premium_users = await PremiumManager.get_all_premium_users()

    # Build and update list
    list_msg, keyboard = PremiumMessageBuilder.build_list_message(premium_users, page)

    try:
        await query.edit_message_text(list_msg, reply_markup=keyboard)
    except:
        await query.answer("Already on this page!", show_alert=False)


@Client.on_callback_query(filters.regex('^prem$'))
async def premium_info_callback(client: Client, query: CallbackQuery):
    """Handle premium info button"""

    status = await PremiumManager.check_premium(query.from_user.id)

    if status.get("is_premium"):
        time_left = PremiumManager.format_time_remaining(
            status["days_left"],
            status["hours_left"]
        )
        expiry = status["expiry_date"].strftime('%d %b %Y')

        await query.answer(
            f"✅ Premium Active!\n⏳ {time_left} remaining (until {expiry})",
            show_alert=True
        )
    else:
        await query.answer(
            "💎 Contact admin to get premium access!\n\n"
            "Benefits: No ads, Direct links, Priority support",
            show_alert=True
        )


# ==================== Premium Expiry Monitor ====================

async def premium_expiry_monitor():
    """
    Background task to monitor and remove expired premium users
    Runs every 1 minute
    """
    print("🔄 Premium expiry monitor started")

    while True:
        try:
            await asyncio.sleep(60)  # Check every 1 minute

            all_users = await kingdb.full_userbase()
            expired_count = 0

            for user_id in all_users:
                try:
                    status = await PremiumManager.check_premium(user_id)

                    # If expired flag is set, user was just removed
                    if status.get("expired"):
                        expired_count += 1
                        print(f"🗑️ Removed expired premium for user: {user_id}")

                        # Try to notify user about expiry
                        try:
                            await Bot.send_message(
                                chat_id=user_id,
                                text=(
                                    f"<blockquote expandable>⏰ 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙀𝙭𝙥𝙞𝙧𝙚𝙙</blockquote>\n\n"
                                    f"Your premium subscription has ended.\n\n"
                                    f"💎 <b>Want to continue?</b>\n"
                                    f"Contact admin to renew your premium access!\n\n"
                                    f"<i>Thank you for being a premium member!</i> 💖"
                                )
                            )
                        except Exception as e:
                            print(f"Failed to notify expired user {user_id}: {e}")

                except Exception as e:
                    print(f"Error checking user {user_id}: {e}")
                    continue

            if expired_count > 0:
                print(f"✅ Premium monitor: Removed {expired_count} expired user(s)")

        except Exception as e:
            print(f"❌ Error in premium expiry monitor: {e}")
            await asyncio.sleep(60)  # Wait before retrying


# ==================== Auto-start Monitor ====================

async def start_monitor_command(client: Client, message: Message):
    """Manually start the premium expiry monitor (admin only)"""

    if message.from_user.id not in OWNER_ID:
        return await message.reply_text("⛔ Owner only command!")

    asyncio.create_task(premium_expiry_monitor())

    await message.reply_text(
        "<blockquote expandable>✅ 𝙈𝙤𝙣𝙞𝙩𝙤𝙧 𝙎𝙩𝙖𝙧𝙩𝙚𝙙</blockquote>\n\n"
        "🔄 Premium expiry monitor is now running\n\n"
        "ℹ️ <i>Checks every 1 minute for expired users</i>"
    )


# Start monitor automatically when bot starts

QR_IMG_LINK = "https://i.ibb.co/5xtpFb2T/f4faad6ca1c1.jpg"


async def prem(client, query):
    text = "🌟 <b>Premium Access</b> 🌟<b>\n</b><blockquote expandable><b><i>🔥 Elevate your experience with Premium Access! 🔥</i></b></blockquote>\n\n<b>💸 ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴs:\n➥ ₹40 - </b>1 ᴍᴏɴᴛʜ ᴀᴄᴄᴇss<b>\n➥ ₹199 - </b>6 ᴍᴏɴᴛʜ ᴀᴄᴄᴇss<b>\n➥ ₹399 - </b>1 ʏᴇᴀʀ ᴀᴄᴄᴇss\n\n<blockquote expandable>🛍 <b>ʜᴏᴡ ᴛᴏ ᴘᴜʀᴄʜᴀsᴇ ᴘʀᴇᴍɪᴜᴍ -</b>\n\n💫 <b>sᴄᴀɴ</b> ᴛʜᴇ ǫʀ ᴄᴏᴅᴇ Ꭺʙᴏvᴇ.\n💫 <b>sᴇɴᴅ</b> ᴛʜᴇ ᴄᴏʀʀᴇᴄᴛ ᴀᴍᴏᴜɴᴛ ᴀᴄᴄᴏʀᴅɪɴɢ ᴛᴏ ᴛʜᴇ ᴘʟᴀɴ ʏᴏᴜ ᴡᴀɴᴛ.\n💫 <b>ʀᴇᴘᴏʀᴛ</b> ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ ᴛᴏ ᴛʜᴇ ᴏᴡɴᴇʀ ᴜsɪɴɢ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ!                                              \n</blockquote>📨 𝚄𝙿𝙸 𝙸𝙳: upi@upi \n\n<blockquote expandable>🎉 <i>Premium Benefits:\n🔅Unlimited Access\n🔅 No Ads\n🔅 Faster Experience\n🔅 Priority Support</i>                                            </blockquote>\n\n<b>⚠️ </b>ɪᴍᴘᴏʀᴛᴀɴᴛ ɴᴏᴛᴇ ⚠️:\n📌 <i>Send the correct amount as per the plan.\n📌 No refunds once the transaction is make.</i>\n\n<blockquote expandable><b><i>🙌 Success starts when you invest in yourself. Unlock the best with Premium.</i></b></blockquote>"
    key = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("ꜱᴇɴᴅ ᴘʀᴏᴏꜰ 🗞️", url="t.me/JD_Namikaze")],
            [InlineKeyboardButton("ᴄᴀɴᴄᴇʟ ", callback_data=f"close")],
        ]
    )
    await query.message.delete()
    await client.send_photo(
        photo=QR_IMG_LINK,
        caption=text,
        reply_markup=key,
        chat_id=query.from_user.id,
    )



