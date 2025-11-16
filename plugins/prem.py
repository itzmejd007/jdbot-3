import asyncio
import logging
from datetime import datetime, timedelta
from bot import Bot
from config import OWNER_ID, LOGGER
from database.database import kingdb
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode, ChatAction
from helper_func import is_admin


logging = logging.getLogger(__name__)   

# ==================== Helper Functions ====================
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


# ==================== Premium Manager Class ====================
class PremiumManager:
    """Centralized premium management system with optimized storage"""

    PREMIUM_SET_KEY = "premium_users_set"  # Key for the set of premium users
    
    @staticmethod
    async def _get_premium_set() -> dict:
        """
        Get the premium users set from database
        Returns: dict with user_id as key and premium data as value
        """
        premium_set = await kingdb.get_variable(PremiumManager.PREMIUM_SET_KEY)
        return premium_set if premium_set else {}
    
    @staticmethod
    async def _save_premium_set(premium_set: dict) -> None:
        """
        Save the premium users set to database
        
        Args:
            premium_set: Dictionary of premium users
        """
        await kingdb.set_variable(PremiumManager.PREMIUM_SET_KEY, premium_set)

    @staticmethod
    async def add_premium(user_id: int, duration_seconds: int, added_by: int) -> dict:
        """
        Add premium access to a user
        Returns: dict with success status and message
        """
        try:
            expiry_date = datetime.now() + timedelta(seconds=duration_seconds)
            
            # Get premium set
            premium_set = await PremiumManager._get_premium_set()
            
            # Add/Update user in premium set
            premium_set[str(user_id)] = {
                "expiry": expiry_date.isoformat(),
                "added_by": added_by,
                "added_at": datetime.now().isoformat(),
                "duration_seconds": duration_seconds
            }
            
            # Save updated set
            await PremiumManager._save_premium_set(premium_set)

            return {
                "success": True,
                "expiry_date": expiry_date,
                "message": f"Premium added successfully until {expiry_date.strftime('%d %b %Y, %I:%M %p')}"
            }
        except Exception as e:
            logging.error(f"Error adding premium for user {user_id}: {e}")
            return {
                "success": False,
                "message": f"Failed to add premium: {str(e)}"
            }

    @staticmethod
    async def remove_premium(user_id: int) -> dict:
        """Remove premium access from a user"""
        try:
            # Get premium set
            premium_set = await PremiumManager._get_premium_set()
            
            user_key = str(user_id)
            
            if user_key not in premium_set:
                return {
                    "success": False,
                    "message": "User doesn't have premium access"
                }
            
            # Remove user from set
            del premium_set[user_key]
            
            # Save updated set
            await PremiumManager._save_premium_set(premium_set)

            return {
                "success": True,
                "message": "Premium access removed successfully"
            }
        except Exception as e:
            logging.error(f"Error removing premium for user {user_id}: {e}")
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
            # Get premium set
            premium_set = await PremiumManager._get_premium_set()
            
            user_key = str(user_id)
            
            if user_key not in premium_set:
                return {
                    "is_premium": False,
                    "message": "User doesn't have premium access"
                }
            
            premium_data = premium_set[user_key]
            expiry = datetime.fromisoformat(premium_data["expiry"])
            now = datetime.now()

            if expiry < now:
                # Premium expired - remove from set
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
            logging.error(f"Error checking premium for user {user_id}: {e}")
            return {
                "is_premium": False,
                "error": True,
                "message": f"Error checking premium: {str(e)}"
            }

    @staticmethod
    async def get_all_premium_users() -> list:
        """Get list of all premium users with their details"""
        try:
            premium_set = await PremiumManager._get_premium_set()
            premium_users = []
            
            # Get current time once
            now = datetime.now()
            expired_users = []

            for user_id_str, premium_data in premium_set.items():
                try:
                    user_id = int(user_id_str)
                    expiry = datetime.fromisoformat(premium_data["expiry"])
                    
                    # Check if expired
                    if expiry < now:
                        expired_users.append(user_id)
                        continue
                    
                    time_left = expiry - now
                    days_left = time_left.days
                    hours_left = time_left.seconds // 3600
                    
                    premium_users.append({
                        "user_id": user_id,
                        "is_premium": True,
                        "expiry_date": expiry,
                        "days_left": days_left,
                        "hours_left": hours_left,
                        "added_by": premium_data.get("added_by"),
                        "added_at": premium_data.get("added_at"),
                        "duration_seconds": premium_data.get("duration_seconds", 0)
                    })
                except Exception as e:
                    logging.error(f"Error processing premium user {user_id_str}: {e}")
                    continue
            
            # Clean up expired users
            if expired_users:
                for user_id in expired_users:
                    await PremiumManager.remove_premium(user_id)
                logging.info(f"Cleaned up {len(expired_users)} expired premium users")
            
            return premium_users
            
        except Exception as e:
            logging.error(f"Error fetching premium users: {e}")
            return []

    @staticmethod
    async def get_premium_count() -> int:
        """Get total count of active premium users"""
        try:
            premium_set = await PremiumManager._get_premium_set()
            return len(premium_set)
        except Exception as e:
            logging.error(f"Error getting premium count: {e}")
            return 0

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
                InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close")]])
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

        buttons.append([
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_list_{page}"),
            InlineKeyboardButton("📊 Stats", callback_data="refresh_stats")
        ])
        buttons.append([
            InlineKeyboardButton("📤 Export", callback_data="export_premium"),
            InlineKeyboardButton("❌ Close", callback_data="close")
        ])

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
            logging.error(f"Failed to notify user {user_id}: {e}")
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
            logging.error(f"Failed to notify user {user_id}: {e}")
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
        logging.error(f"Error in list premium command: {e}")
        await message.reply_text(
            f"<blockquote expandable>❌ 𝙀𝙧𝙧𝙤𝙧</blockquote>\n\n"
            f"<b>Failed to fetch premium users:</b>\n"
            f"<code>{str(e)}</code>"
        )


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


@Client.on_message(filters.command('premstats') & filters.private)
async def premium_stats_command(client: Client, message: Message):
    """Show premium statistics (admin only)"""
    await message.reply_chat_action(ChatAction.TYPING)

    # Check if user is admin
    if not await is_admin(0, 0, message.from_user.id):
        return await message.reply_text(
            "<blockquote expandable>⛔ 𝘼𝙘𝙘𝙚𝙨𝙨 𝘿𝙚𝙣𝙞𝙚𝙙</blockquote>\n\n"
            "❌ <i>Only admins can view statistics</i>"
        )

    try:
        premium_users = await PremiumManager.get_all_premium_users()
        total_count = len(premium_users)
        
        if total_count == 0:
            return await message.reply_text(
                "<blockquote expandable>📊 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙎𝙩𝙖𝙩𝙞𝙨𝙩𝙞𝙘𝙨</blockquote>\n\n"
                "ℹ️ <i>No premium users currently</i>"
            )
        
        # Calculate statistics
        expiring_soon = sum(1 for user in premium_users if user["days_left"] <= 7)
        expiring_today = sum(1 for user in premium_users if user["days_left"] == 0)
        
        stats_text = (
            f"<blockquote expandable>📊 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙎𝙩𝙖𝙩𝙞𝙨𝙩𝙞𝙘𝙨</blockquote>\n\n"
            f"👥 <b>Total Premium Users:</b> <code>{total_count}</code>\n"
            f"⚠️ <b>Expiring in 7 Days:</b> <code>{expiring_soon}</code>\n"
            f"🔴 <b>Expiring Today:</b> <code>{expiring_today}</code>\n\n"
        )
        
        # Show top 5 users with most time left
        sorted_users = sorted(premium_users, key=lambda x: x["days_left"], reverse=True)[:5]
        
        if sorted_users:
            stats_text += "<b>🏆 Top Premium Users:</b>\n\n"
            for idx, user in enumerate(sorted_users, 1):
                time_left = PremiumManager.format_time_remaining(user["days_left"], user["hours_left"])
                stats_text += f"<b>{idx}.</b> <code>{user['user_id']}</code> - <i>{time_left}</i>\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 View Full List", callback_data="prem_list_1")],
            [InlineKeyboardButton("📜 View History", callback_data="refresh_history")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")],
            [InlineKeyboardButton("📤 Export", callback_data="export_premium")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
        
        await message.reply_text(stats_text, reply_markup=keyboard)
        
    except Exception as e:
        logging.error(f"Error in premium stats: {e}")
        await message.reply_text(
            f"<blockquote expandable>❌ 𝙀𝙧𝙧𝙤𝙧</blockquote>\n\n"
            f"<code>{str(e)}</code>"
        )


# ==================== Callback Query Handlers ====================

@Client.on_callback_query(filters.regex(r'^prem_list_(\d+)$'))
async def premium_list_pagination(client: Client, query: CallbackQuery):
    """Handle premium list pagination"""

    # Check if user is admin
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can view this!", show_alert=True)

    page = int(query.data.split('_')[-1])

    # Get all premium users
    premium_users = await PremiumManager.get_all_premium_users()

    # Build and update list
    list_msg, keyboard = PremiumMessageBuilder.build_list_message(premium_users, page)

    try:
        await query.edit_message_text(list_msg, reply_markup=keyboard)
        await query.answer()
    except Exception as e:
        await query.answer("Already on this page!", show_alert=False)


@Client.on_callback_query(filters.regex('^prem_stats$'))
async def premium_stats_callback(client: Client, query: CallbackQuery):
    """Handle premium stats refresh"""
    
    # Check if user is admin
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can view this!", show_alert=True)
    
    try:
        premium_users = await PremiumManager.get_all_premium_users()
        total_count = len(premium_users)
        
        if total_count == 0:
            stats_text = (
                "<blockquote expandable>📊 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙎𝙩𝙖𝙩𝙞𝙨𝙩𝙞𝙘𝙨</blockquote>\n\n"
                "ℹ️ <i>No premium users currently</i>"
            )
        else:
            expiring_soon = sum(1 for user in premium_users if user["days_left"] <= 7)
            expiring_today = sum(1 for user in premium_users if user["days_left"] == 0)
            
            stats_text = (
                f"<blockquote expandable>📊 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙎𝙩𝙖𝙩𝙞𝙨𝙩𝙞𝙘𝙨</blockquote>\n\n"
                f"👥 <b>Total Premium Users:</b> <code>{total_count}</code>\n"
                f"⚠️ <b>Expiring in 7 Days:</b> <code>{expiring_soon}</code>\n"
                f"🔴 <b>Expiring Today:</b> <code>{expiring_today}</code>\n\n"
            )
            
            sorted_users = sorted(premium_users, key=lambda x: x["days_left"], reverse=True)[:5]
            
            if sorted_users:
                stats_text += "<b>🏆 Top Premium Users:</b>\n\n"
                for idx, user in enumerate(sorted_users, 1):
                    time_left = PremiumManager.format_time_remaining(user["days_left"], user["hours_left"])
                    stats_text += f"<b>{idx}.</b> <code>{user['user_id']}</code> - <i>{time_left}</i>\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 View Full List", callback_data="prem_list_1")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="prem_stats")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
        
        await query.edit_message_text(stats_text, reply_markup=keyboard)
        await query.answer("Stats refreshed! ✅")
        
    except Exception as e:
        logging.error(f"Error refreshing stats: {e}")
        await query.answer("Failed to refresh stats!", show_alert=True)


@Client.on_callback_query(filters.regex('^prem$'))
async def premium_info_callback(client: Client, query: CallbackQuery):
    """Handle premium purchase info - redirects to purchase page"""
    await prem(client, query)


@Client.on_callback_query(filters.regex('^close$'))
async def close_callback(client: Client, query: CallbackQuery):
    """Handle close button"""
    try:
        await query.message.delete()
    except:
        pass


# ==================== Premium Expiry Monitor ====================

async def premium_expiry_monitor():
    """
    Background task to monitor and remove expired premium users
    Runs every 5 minutes
    """
    logging.info("🔄 Premium expiry monitor started")

    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes

            premium_users = await PremiumManager.get_all_premium_users()
            
            # The get_all_premium_users already removes expired users
            # We just need to notify them
            
            logging.info(f"✅ Premium monitor: Active users checked - {len(premium_users)} premium users")

        except Exception as e:
            logging.error(f"❌ Error in premium expiry monitor: {e}")
            await asyncio.sleep(300)  # Wait before retrying


async def notify_expiring_soon():
    """
    Notify users whose premium is expiring within 24 hours
    Runs once daily
    """
    logging.info("📢 Starting expiring soon notifications")
    
    while True:
        try:
            await asyncio.sleep(86400)  # Run once every 24 hours
            
            premium_users = await PremiumManager.get_all_premium_users()
            
            for user in premium_users:
                # Notify if expiring within 24 hours
                if user["days_left"] == 0 and user["hours_left"] <= 24:
                    try:
                        time_left = PremiumManager.format_time_remaining(
                            user["days_left"],
                            user["hours_left"]
                        )
                        
                        await Bot.send_message(
                            chat_id=user["user_id"],
                            text=(
                                f"<blockquote expandable>⚠️ 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙀𝙭𝙥𝙞𝙧𝙞𝙣𝙜 𝙎𝙤𝙤𝙣</blockquote>\n\n"
                                f"Your premium subscription is expiring soon!\n\n"
                                f"⏳ <b>Time Remaining:</b> <code>{time_left}</code>\n\n"
                                f"💡 <b>Renew now to continue enjoying:</b>\n"
                                f"• 🚫 No ads or verification\n"
                                f"• ⚡ Direct download links\n"
                                f"• 🎯 Priority support\n"
                                f"• 🔓 Unlimited access\n\n"
                                f"<i>Contact admin to renew your premium!</i>"
                            )
                        )
                        logging.info(f"Notified user {user['user_id']} about expiring premium")
                    except Exception as e:
                        logging.error(f"Failed to notify user {user['user_id']}: {e}")
            
        except Exception as e:
            logging.error(f"Error in expiring soon notifications: {e}")
            await asyncio.sleep(86400)


# ==================== Initialization ====================

def start_premium_monitors():
    """Start all premium monitoring tasks"""
    asyncio.create_task(premium_expiry_monitor())
    asyncio.create_task(notify_expiring_soon())
    logging.info("✅ All premium monitors started")


# ==================== Premium Purchase Handler ====================

QR_IMG_LINK = "https://commercial-amethyst-wcs1oyy4pv.edgeone.app/IMG_20251116_131738.jpg"


async def prem(client, query):
    """Handle premium purchase info display"""
    text = (
        "🌟 <b>Premium Access</b> 🌟<b>\n</b>"
        "<blockquote expandable><b><i>🔥 Elevate your experience with Premium Access! 🔥</i></b></blockquote>\n\n"
        "<b>💸 ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴs:\n"
        "➥ ₹40 - </b>1 ᴍᴏɴᴛʜ ᴀᴄᴄᴇss<b>\n"
        "➥ ₹199 - </b>6 ᴍᴏɴᴛʜ ᴀᴄᴄᴇss<b>\n"
        "➥ ₹399 - </b>1 ʏᴇᴀʀ ᴀᴄᴄᴇss\n\n"
        "<blockquote expandable>🛍 <b>ʜᴏᴡ ᴛᴏ ᴘᴜʀᴄʜᴀsᴇ ᴘʀᴇᴍɪᴜᴍ -</b>\n\n"
        "💫 <b>sᴄᴀɴ</b> ᴛʜᴇ ǫʀ ᴄᴏᴅᴇ Ꭺʙᴏvᴇ.\n"
        "💫 <b>sᴇɴᴅ</b> ᴛʜᴇ ᴄᴏʀʀᴇᴄᴛ ᴀᴍᴏᴜɴᴛ ᴀᴄᴄᴏʀᴅɪɴɢ ᴛᴏ ᴛʜᴇ ᴘʟᴀɴ ʏᴏᴜ ᴡᴀɴᴛ.\n"
        "💫 <b>ʀᴇᴘᴏʀᴛ</b> ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ ᴛᴏ ᴛʜᴇ ᴏᴡɴᴇʀ ᴜsɪɴɢ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ!                                              \n"
        "</blockquote>"
        "📨 𝚄𝙿𝙸 𝙸𝙳: upi@upi \n\n"
        "<blockquote expandable>🎉 <i>Premium Benefits:\n"
        "🔅Unlimited Access\n"
        "🔅 No Ads\n"
        "🔅 Faster Experience\n"
        "🔅 Priority Support</i>                                            </blockquote>\n\n"
        "<b>⚠️ </b>ɪᴍᴘᴏʀᴛᴀɴᴛ ɴᴏᴛᴇ ⚠️:\n"
        "📌 <i>Send the correct amount as per the plan.\n"
        "📌 No refunds once the transaction is make.</i>\n\n"
        "<blockquote expandable><b><i>🙌 Success starts when you invest in yourself. Unlock the best with Premium.</i></b></blockquote>"
    )
    
    key = InlineKeyboardMarkup([
        [InlineKeyboardButton("ꜱᴇɴᴅ ᴘʀᴏᴏꜰ 🗞️", url="t.me/JD_Namikaze")],
        [InlineKeyboardButton("ᴄᴀɴᴄᴇʟ ", callback_data="close")],
    ])
    
    await query.message.delete()
    await client.send_photo(
        photo=QR_IMG_LINK,
        caption=text,
        reply_markup=key,
        chat_id=query.from_user.id,
    )


# ==================== Helper Function for Other Modules ====================

async def is_premium_user(user_id: int) -> bool:
    """
    Quick check if a user has active premium
    Can be used by other modules
    
    Args:
        user_id: User ID to check
        
    Returns:
        bool: True if user has active premium, False otherwise
    """
    status = await PremiumManager.check_premium(user_id)
    return status.get("is_premium", False)


# ==================== Bulk Premium Operations ====================

@Client.on_message(filters.command('addpremiumlist') & filters.private)
async def add_premium_bulk_command(client: Client, message: Message):
    """
    Add premium to multiple users at once
    Usage: /addpremiumlist user_id1,user_id2,user_id3 duration
    """
    await message.reply_chat_action(ChatAction.TYPING)

    # Check if user is admin
    if not await is_admin(0, 0, message.from_user.id):
        return await message.reply_text(
            "<blockquote expandable>⛔ 𝘼𝙘𝙘𝙚𝙨𝙨 𝘿𝙚𝙣𝙞𝙚𝙙</blockquote>\n\n"
            "❌ <i>Only admins can use this command</i>"
        )

    args = message.text.split()
    
    if len(args) < 3:
        return await message.reply_text(
            "<blockquote expandable>ℹ️ 𝘽𝙪𝙡𝙠 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙂𝙪𝙞𝙙𝙚</blockquote>\n\n"
            "<b>Usage:</b>\n"
            "<code>/addpremiumlist user_id1,user_id2,user_id3 duration</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/addpremiumlist 123,456,789 1mo</code>\n\n"
            "<i>Separate user IDs with commas (no spaces)</i>"
        )
    
    try:
        user_ids_str = args[1]
        duration_input = args[2].lower()
        
        # Parse user IDs
        user_ids = [int(uid.strip()) for uid in user_ids_str.split(',')]
        
        # Parse duration
        duration_seconds = parse_duration(duration_input)
        if duration_seconds is None or duration_seconds <= 0:
            return await message.reply_text("❌ Invalid duration format!")
        
        duration_display = format_duration_display(duration_seconds)
        
        # Process each user
        success_count = 0
        failed_users = []
        
        status_msg = await message.reply_text(
            f"<b>Processing {len(user_ids)} users...</b>\n\n"
            f"⏳ Please wait..."
        )
        
        for user_id in user_ids:
            result = await PremiumManager.add_premium(user_id, duration_seconds, message.from_user.id)
            
            if result["success"]:
                success_count += 1
                # Try to notify user
                try:
                    await client.send_message(
                        chat_id=user_id,
                        text=(
                            f"<blockquote expandable>🎉 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝘼𝙘𝙩𝙞𝙫𝙖𝙩𝙚𝙙</blockquote>\n\n"
                            f"💎 You've been granted <b>{duration_display}</b> of premium access!\n\n"
                            f"📅 <b>Valid Until:</b> <code>{result['expiry_date'].strftime('%d %b %Y, %I:%M %p')}</code>\n\n"
                            f"✨ <i>Enjoy your premium experience!</i> 🎊"
                        )
                    )
                except:
                    pass
            else:
                failed_users.append(user_id)
        
        # Summary
        summary = (
            f"<blockquote expandable>✅ 𝘽𝙪𝙡𝙠 𝙊𝙥𝙚𝙧𝙖𝙩𝙞𝙤𝙣 𝘾𝙤𝙢𝙥𝙡𝙚𝙩𝙚</blockquote>\n\n"
            f"📊 <b>Results:</b>\n"
            f"✅ Success: <code>{success_count}</code>\n"
            f"❌ Failed: <code>{len(failed_users)}</code>\n"
            f"📝 Total: <code>{len(user_ids)}</code>\n\n"
            f"⏰ <b>Duration:</b> <code>{duration_display}</code>\n"
        )
        
        if failed_users:
            summary += f"\n<b>Failed IDs:</b> <code>{', '.join(map(str, failed_users))}</code>"
        
        await status_msg.edit_text(summary)
        
    except ValueError:
        await message.reply_text("❌ Invalid user ID format! Make sure all IDs are numbers.")
    except Exception as e:
        logging.error(f"Bulk premium error: {e}")
        await message.reply_text(f"❌ Error: <code>{str(e)}</code>")


@Client.on_message(filters.command('extendpremium') & filters.private)
async def extend_premium_command(client: Client, message: Message):
    """
    Extend existing premium subscription
    Usage: /extendpremium user_id duration
    """
    await message.reply_chat_action(ChatAction.TYPING)

    # Check if user is admin
    if not await is_admin(0, 0, message.from_user.id):
        return await message.reply_text(
            "<blockquote expandable>⛔ 𝘼𝙘𝙘𝙚𝙨𝙨 𝘿𝙚𝙣𝙞𝙚𝙙</blockquote>\n\n"
            "❌ <i>Only admins can use this command</i>"
        )

    args = message.text.split()
    
    if len(args) < 3:
        return await message.reply_text(
            "<blockquote expandable>ℹ️ 𝙀𝙭𝙩𝙚𝙣𝙙 𝙋𝙧𝙚𝙢𝙞𝙪𝙢</blockquote>\n\n"
            "<b>Usage:</b>\n"
            "<code>/extendpremium user_id duration</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/extendpremium 123456789 1mo</code>\n\n"
            "<i>This will add time to their existing premium</i>"
        )
    
    try:
        user_id = int(args[1])
        duration_input = args[2].lower()
        
        # Parse duration
        duration_seconds = parse_duration(duration_input)
        if duration_seconds is None or duration_seconds <= 0:
            return await message.reply_text("❌ Invalid duration format!")
        
        # Check current premium status
        status = await PremiumManager.check_premium(user_id)
        
        if not status.get("is_premium"):
            return await message.reply_text(
                "❌ User doesn't have active premium!\n\n"
                "💡 Use <code>/addpremium</code> instead."
            )
        
        # Get premium set and extend
        premium_set = await PremiumManager._get_premium_set()
        user_key = str(user_id)
        
        current_expiry = datetime.fromisoformat(premium_set[user_key]["expiry"])
        new_expiry = current_expiry + timedelta(seconds=duration_seconds)
        
        # Update expiry
        premium_set[user_key]["expiry"] = new_expiry.isoformat()
        premium_set[user_key]["duration_seconds"] += duration_seconds
        
        await PremiumManager._save_premium_set(premium_set)
        
        duration_display = format_duration_display(duration_seconds)
        
        await message.reply_text(
            f"<blockquote expandable>✅ 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙀𝙭𝙩𝙚𝙣𝙙𝙚𝙙</blockquote>\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"➕ <b>Added:</b> <code>{duration_display}</code>\n"
            f"📅 <b>New Expiry:</b> <code>{new_expiry.strftime('%d %b %Y, %I:%M %p')}</code>\n\n"
            f"✨ <i>Premium extended successfully!</i>"
        )
        
        # Notify user
        try:
            await client.send_message(
                chat_id=user_id,
                text=(
                    f"<blockquote expandable>🎉 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙀𝙭𝙩𝙚𝙣𝙙𝙚𝙙</blockquote>\n\n"
                    f"Your premium has been extended by <b>{duration_display}</b>!\n\n"
                    f"📅 <b>New Expiry:</b> <code>{new_expiry.strftime('%d %b %Y, %I:%M %p')}</code>\n\n"
                    f"✨ <i>Continue enjoying premium benefits!</i> 🎊"
                )
            )
        except:
            pass
        
    except ValueError:
        await message.reply_text("❌ Invalid user ID!")
    except Exception as e:
        logging.error(f"Extend premium error: {e}")
        await message.reply_text(f"❌ Error: <code>{str(e)}</code>")


# ==================== Premium Data Export ====================

@Client.on_message(filters.command('exportpremium') & filters.private)
async def export_premium_command(client: Client, message: Message):
    """
    Export premium users data to a file
    """
    await message.reply_chat_action(ChatAction.TYPING)

    # Check if user is admin
    if not await is_admin(0, 0, message.from_user.id):
        return await message.reply_text(
            "<blockquote expandable>⛔ 𝘼𝙘𝙘𝙚𝙨𝙨 𝘿𝙚𝙣𝙞𝙚𝙙</blockquote>\n\n"
            "❌ <i>Only admins can use this command</i>"
        )

    try:
        premium_users = await PremiumManager.get_all_premium_users()
        
        if not premium_users:
            return await message.reply_text("ℹ️ No premium users to export")
        
        # Create export text
        export_text = "=" * 50 + "\n"
        export_text += "PREMIUM USERS EXPORT\n"
        export_text += f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
        export_text += f"Total Users: {len(premium_users)}\n"
        export_text += "=" * 50 + "\n\n"
        
        for idx, user in enumerate(premium_users, 1):
            time_left = PremiumManager.format_time_remaining(user["days_left"], user["hours_left"])
            expiry = user["expiry_date"].strftime('%d %b %Y, %I:%M %p')
            added_at = datetime.fromisoformat(user["added_at"]).strftime('%d %b %Y, %I:%M %p')
            duration = format_duration_display(user["duration_seconds"])
            
            export_text += f"{idx}. USER ID: {user['user_id']}\n"
            export_text += f"   Time Left: {time_left}\n"
            export_text += f"   Expires: {expiry}\n"
            export_text += f"   Added: {added_at}\n"
            export_text += f"   Added By: {user['added_by']}\n"
            export_text += f"   Duration: {duration}\n"
            export_text += "-" * 50 + "\n\n"
        
        # Save to file
        filename = f"premium_users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(export_text)
        
        # Send file
        await message.reply_document(
            document=filename,
            caption=(
                f"<b>📊 Premium Users Export</b>\n\n"
                f"👥 Total: <code>{len(premium_users)}</code>\n"
                f"📅 Generated: <code>{datetime.now().strftime('%d %b %Y, %I:%M %p')}</code>"
            )
        )
        
        # Delete file
        import os
        os.remove(filename)
        
    except Exception as e:
        logging.error(f"Export error: {e}")
        await message.reply_text(f"❌ Export failed: <code>{str(e)}</code>")


# ==================== Premium Search ====================

@Client.on_message(filters.command('searchpremium') & filters.private)
async def search_premium_command(client: Client, message: Message):
    """
    Search for a specific premium user
    Usage: /searchpremium user_id
    """
    await message.reply_chat_action(ChatAction.TYPING)

    # Check if user is admin
    if not await is_admin(0, 0, message.from_user.id):
        return await message.reply_text(
            "<blockquote expandable>⛔ 𝘼𝙘𝙘𝙚𝙨𝙨 𝘿𝙚𝙣𝙞𝙚𝙙</blockquote>\n\n"
            "❌ <i>Only admins can use this command</i>"
        )

    args = message.text.split()
    
    if len(args) < 2:
        return await message.reply_text(
            "<blockquote expandable>ℹ️ 𝙎𝙚𝙖𝙧𝙘𝙝 𝙋𝙧𝙚𝙢𝙞𝙪𝙢</blockquote>\n\n"
            "<b>Usage:</b>\n"
            "<code>/searchpremium user_id</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/searchpremium 123456789</code>"
        )
    
    try:
        user_id = int(args[1])
        status = await PremiumManager.check_premium(user_id)
        
        # Build detailed status message
        status_msg = PremiumMessageBuilder.build_status_message(user_id, status)
        
        # Add quick actions
        if status.get("is_premium"):
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 Extend", callback_data=f"extend_menu_{user_id}"),
                    InlineKeyboardButton("🗑️ Remove", callback_data=f"confirm_remove_{user_id}")
                ],
                [InlineKeyboardButton("🔄 Refresh", callback_data=f"search_premium_{user_id}")],
                [InlineKeyboardButton("❌ Close", callback_data="close")]
            ])
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Premium", callback_data=f"add_menu_{user_id}")],
                [InlineKeyboardButton("🔄 Refresh", callback_data=f"search_premium_{user_id}")],
                [InlineKeyboardButton("❌ Close", callback_data="close")]
            ])
        
        await message.reply_text(status_msg, reply_markup=keyboard)
        
    except ValueError:
        await message.reply_text("❌ Invalid user ID! User ID must be a number.")


# ==================== Premium History ====================

@Client.on_message(filters.command('premiumhistory') & filters.private)
async def premium_history_command(client: Client, message: Message):
    """
    View premium addition history
    Shows recent premium additions
    """
    await message.reply_chat_action(ChatAction.TYPING)

    # Check if user is admin
    if not await is_admin(0, 0, message.from_user.id):
        return await message.reply_text(
            "<blockquote expandable>⛔ 𝘼𝙘𝙘𝙚𝙨𝙨 𝘿𝙚𝙣𝙞𝙚𝙙</blockquote>\n\n"
            "❌ <i>Only admins can use this command</i>"
        )

    try:
        premium_users = await PremiumManager.get_all_premium_users()
        
        if not premium_users:
            return await message.reply_text(
                "<blockquote expandable>📜 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙃𝙞𝙨𝙩𝙤𝙧𝙮</blockquote>\n\n"
                "ℹ️ <i>No premium history available</i>"
            )
        
        # Sort by added date (most recent first)
        sorted_users = sorted(
            premium_users,
            key=lambda x: datetime.fromisoformat(x["added_at"]),
            reverse=True
        )[:20]  # Show last 20
        
        history_text = (
            f"<blockquote expandable>📜 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙃𝙞𝙨𝙩𝙤𝙧𝙮</blockquote>\n\n"
            f"<b>Recent Additions (Last 20):</b>\n\n"
        )
        
        for idx, user in enumerate(sorted_users, 1):
            added_at = datetime.fromisoformat(user["added_at"]).strftime('%d %b %y, %I:%M %p')
            duration = format_duration_display(user["duration_seconds"])
            
            history_text += (
                f"<b>{idx}.</b> 👤 <code>{user['user_id']}</code>\n"
                f"   📅 {added_at}\n"
                f"   ⏰ {duration}\n"
                f"   👨‍💼 By: <code>{user['added_by']}</code>\n\n"
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 View Stats", callback_data="refresh_stats")],
            [InlineKeyboardButton("📋 View List", callback_data="prem_list_1")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_history")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
        
        await message.reply_text(history_text, reply_markup=keyboard)
        
    except Exception as e:
        logging.error(f"History error: {e}")
        await message.reply_text(f"❌ Error: <code>{str(e)}</code>")


# ==================== Advanced Callback Handlers ====================

@Client.on_callback_query(filters.regex(r'^search_premium_(\d+)$'))
async def search_premium_callback(client: Client, query: CallbackQuery):
    """Handle search premium refresh"""
    
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can view this!", show_alert=True)
    
    user_id = int(query.data.split('_')[-1])
    
    try:
        status = await PremiumManager.check_premium(user_id)
        status_msg = PremiumMessageBuilder.build_status_message(user_id, status)
        
        # Build action keyboard
        if status.get("is_premium"):
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 Extend", callback_data=f"extend_menu_{user_id}"),
                    InlineKeyboardButton("🗑️ Remove", callback_data=f"confirm_remove_{user_id}")
                ],
                [InlineKeyboardButton("🔄 Refresh", callback_data=f"search_premium_{user_id}")],
                [InlineKeyboardButton("❌ Close", callback_data="close")]
            ])
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Premium", callback_data=f"add_menu_{user_id}")],
                [InlineKeyboardButton("🔄 Refresh", callback_data=f"search_premium_{user_id}")],
                [InlineKeyboardButton("❌ Close", callback_data="close")]
            ])
        
        await query.edit_message_text(status_msg, reply_markup=keyboard)
        await query.answer("Refreshed! ✅")
        
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)


@Client.on_callback_query(filters.regex(r'^extend_menu_(\d+)$'))
async def extend_menu_callback(client: Client, query: CallbackQuery):
    """Show extend duration options"""
    
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can do this!", show_alert=True)
    
    user_id = int(query.data.split('_')[-1])
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("7 Days", callback_data=f"extend_{user_id}_7d"),
            InlineKeyboardButton("15 Days", callback_data=f"extend_{user_id}_15d")
        ],
        [
            InlineKeyboardButton("1 Month", callback_data=f"extend_{user_id}_1mo"),
            InlineKeyboardButton("3 Months", callback_data=f"extend_{user_id}_3mo")
        ],
        [
            InlineKeyboardButton("6 Months", callback_data=f"extend_{user_id}_6mo"),
            InlineKeyboardButton("1 Year", callback_data=f"extend_{user_id}_1y")
        ],
        [InlineKeyboardButton("◀️ Back", callback_data=f"search_premium_{user_id}")]
    ])
    
    await query.edit_message_text(
        f"<b>🔄 Extend Premium</b>\n\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n\n"
        f"<b>Select duration to extend:</b>",
        reply_markup=keyboard
    )


@Client.on_callback_query(filters.regex(r'^extend_(\d+)_(.+)$'))
async def extend_premium_callback(client: Client, query: CallbackQuery):
    """Actually extend premium"""
    
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can do this!", show_alert=True)
    
    parts = query.data.split('_')
    user_id = int(parts[1])
    duration_input = parts[2]
    
    try:
        # Parse duration
        duration_seconds = parse_duration(duration_input)
        if not duration_seconds:
            return await query.answer("Invalid duration!", show_alert=True)
        
        # Get premium set and extend
        premium_set = await PremiumManager._get_premium_set()
        user_key = str(user_id)
        
        if user_key not in premium_set:
            return await query.answer("User doesn't have premium!", show_alert=True)
        
        current_expiry = datetime.fromisoformat(premium_set[user_key]["expiry"])
        new_expiry = current_expiry + timedelta(seconds=duration_seconds)
        
        # Update expiry
        premium_set[user_key]["expiry"] = new_expiry.isoformat()
        premium_set[user_key]["duration_seconds"] += duration_seconds
        
        await PremiumManager._save_premium_set(premium_set)
        
        duration_display = format_duration_display(duration_seconds)
        
        await query.edit_message_text(
            f"<blockquote expandable>✅ 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙀𝙭𝙩𝙚𝙣𝙙𝙚𝙙</blockquote>\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"➕ <b>Added:</b> <code>{duration_display}</code>\n"
            f"📅 <b>New Expiry:</b> <code>{new_expiry.strftime('%d %b %Y, %I:%M %p')}</code>\n\n"
            f"✨ <i>Premium extended successfully!</i>"
        )
        
        # Notify user
        try:
            await client.send_message(
                chat_id=user_id,
                text=(
                    f"<blockquote expandable>🎉 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙀𝙭𝙩𝙚𝙣𝙙𝙚𝙙</blockquote>\n\n"
                    f"Your premium has been extended by <b>{duration_display}</b>!\n\n"
                    f"📅 <b>New Expiry:</b> <code>{new_expiry.strftime('%d %b %Y, %I:%M %p')}</code>\n\n"
                    f"✨ <i>Continue enjoying premium benefits!</i> 🎊"
                )
            )
        except:
            pass
        
        await query.answer("Premium extended! ✅")
        
    except Exception as e:
        logging.error(f"Extend error: {e}")
        await query.answer(f"Error: {str(e)}", show_alert=True)


@Client.on_callback_query(filters.regex(r'^add_menu_(\d+)$'))
async def add_menu_callback(client: Client, query: CallbackQuery):
    """Show add premium duration options"""
    
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can do this!", show_alert=True)
    
    user_id = int(query.data.split('_')[-1])
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("7 Days", callback_data=f"add_{user_id}_7d"),
            InlineKeyboardButton("15 Days", callback_data=f"add_{user_id}_15d")
        ],
        [
            InlineKeyboardButton("1 Month", callback_data=f"add_{user_id}_1mo"),
            InlineKeyboardButton("3 Months", callback_data=f"add_{user_id}_3mo")
        ],
        [
            InlineKeyboardButton("6 Months", callback_data=f"add_{user_id}_6mo"),
            InlineKeyboardButton("1 Year", callback_data=f"add_{user_id}_1y")
        ],
        [InlineKeyboardButton("◀️ Back", callback_data=f"search_premium_{user_id}")]
    ])
    
    await query.edit_message_text(
        f"<b>➕ Add Premium</b>\n\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n\n"
        f"<b>Select duration:</b>",
        reply_markup=keyboard
    )


@Client.on_callback_query(filters.regex(r'^add_(\d+)_(.+)$'))
async def add_premium_callback(client: Client, query: CallbackQuery):
    """Actually add premium via callback"""
    
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can do this!", show_alert=True)
    
    parts = query.data.split('_')
    user_id = int(parts[1])
    duration_input = parts[2]
    
    try:
        # Parse duration
        duration_seconds = parse_duration(duration_input)
        if not duration_seconds:
            return await query.answer("Invalid duration!", show_alert=True)
        
        # Add premium
        result = await PremiumManager.add_premium(user_id, duration_seconds, query.from_user.id)
        
        if result["success"]:
            duration_display = format_duration_display(duration_seconds)
            
            await query.edit_message_text(
                PremiumMessageBuilder.build_add_success_message(
                    user_id,
                    result["expiry_date"],
                    duration_display
                )
            )
            
            # Notify user
            try:
                await client.send_message(
                    chat_id=user_id,
                    text=(
                        f"<blockquote expandable>🎉 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝘼𝙘𝙩𝙞𝙫𝙖𝙩𝙚𝙙</blockquote>\n\n"
                        f"💎 You've been granted <b>{duration_display}</b> of premium access!\n\n"
                        f"📅 <b>Valid Until:</b> <code>{result['expiry_date'].strftime('%d %b %Y, %I:%M %p')}</code>\n\n"
                        f"✨ <i>Enjoy your premium experience!</i> 🎊"
                    )
                )
            except:
                pass
            
            await query.answer("Premium added! ✅")
        else:
            await query.answer(result["message"], show_alert=True)
            
    except Exception as e:
        logging.error(f"Add premium error: {e}")
        await query.answer(f"Error: {str(e)}", show_alert=True)


@Client.on_callback_query(filters.regex(r'^confirm_remove_(\d+)$'))
async def confirm_remove_callback(client: Client, query: CallbackQuery):
    """Confirm premium removal"""
    
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can do this!", show_alert=True)
    
    user_id = int(query.data.split('_')[-1])
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Remove", callback_data=f"remove_{user_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"search_premium_{user_id}")
        ]
    ])
    
    await query.edit_message_text(
        f"<b>⚠️ Confirm Action</b>\n\n"
        f"Are you sure you want to remove premium from user <code>{user_id}</code>?\n\n"
        f"<i>This action cannot be undone!</i>",
        reply_markup=keyboard
    )


@Client.on_callback_query(filters.regex(r'^remove_(\d+)$'))
async def remove_premium_callback(client: Client, query: CallbackQuery):
    """Actually remove premium"""
    
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can do this!", show_alert=True)
    
    user_id = int(query.data.split('_')[-1])
    
    result = await PremiumManager.remove_premium(user_id)
    
    if result["success"]:
        await query.edit_message_text(
            PremiumMessageBuilder.build_remove_success_message(user_id)
        )
        
        # Notify user
        try:
            await client.send_message(
                chat_id=user_id,
                text=(
                    f"<blockquote expandable>ℹ️ 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙀𝙭𝙥𝙞𝙧𝙚𝙙</blockquote>\n\n"
                    f"Your premium access has ended.\n\n"
                    f"💡 <i>Contact admin to renew premium access</i>"
                )
            )
        except:
            pass
        
        await query.answer("Premium removed successfully! ✅")
    else:
        await query.answer(result["message"], show_alert=True)


@Client.on_callback_query(filters.regex(r'^refresh_list_(\d+)$'))
async def refresh_list_callback(client: Client, query: CallbackQuery):
    """Refresh premium list"""
    
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can view this!", show_alert=True)
    
    page = int(query.data.split('_')[-1])
    
    try:
        premium_users = await PremiumManager.get_all_premium_users()
        list_msg, keyboard = PremiumMessageBuilder.build_list_message(premium_users, page)
        
        await query.edit_message_text(list_msg, reply_markup=keyboard)
        await query.answer("List refreshed! ✅")
        
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)


@Client.on_callback_query(filters.regex(r'^refresh_stats$'))
async def refresh_stats_callback(client: Client, query: CallbackQuery):
    """Refresh premium stats"""
    
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can view this!", show_alert=True)
    
    try:
        premium_users = await PremiumManager.get_all_premium_users()
        total_count = len(premium_users)
        
        if total_count == 0:
            stats_text = (
                "<blockquote expandable>📊 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙎𝙩𝙖𝙩𝙞𝙨𝙩𝙞𝙘𝙨</blockquote>\n\n"
                "ℹ️ <i>No premium users currently</i>"
            )
        else:
            expiring_soon = sum(1 for user in premium_users if user["days_left"] <= 7)
            expiring_today = sum(1 for user in premium_users if user["days_left"] == 0)
            
            stats_text = (
                f"<blockquote expandable>📊 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙎𝙩𝙖𝙩𝙞𝙨𝙩𝙞𝙘𝙨</blockquote>\n\n"
                f"👥 <b>Total Premium Users:</b> <code>{total_count}</code>\n"
                f"⚠️ <b>Expiring in 7 Days:</b> <code>{expiring_soon}</code>\n"
                f"🔴 <b>Expiring Today:</b> <code>{expiring_today}</code>\n\n"
            )
            
            sorted_users = sorted(premium_users, key=lambda x: x["days_left"], reverse=True)[:5]
            
            if sorted_users:
                stats_text += "<b>🏆 Top Premium Users:</b>\n\n"
                for idx, user in enumerate(sorted_users, 1):
                    time_left = PremiumManager.format_time_remaining(user["days_left"], user["hours_left"])
                    stats_text += f"<b>{idx}.</b> <code>{user['user_id']}</code> - <i>{time_left}</i>\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 View Full List", callback_data="prem_list_1")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
        
        await query.edit_message_text(stats_text, reply_markup=keyboard)
        await query.answer("Stats refreshed! ✅")
        
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)


@Client.on_callback_query(filters.regex(r'^refresh_history$'))
async def refresh_history_callback(client: Client, query: CallbackQuery):
    """Refresh premium history"""
    
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can view this!", show_alert=True)
    
    try:
        premium_users = await PremiumManager.get_all_premium_users()
        
        if not premium_users:
            history_text = (
                f"<blockquote expandable>📜 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙃𝙞𝙨𝙩𝙤𝙧𝙮</blockquote>\n\n"
                "ℹ️ <i>No premium history available</i>"
            )
        else:
            sorted_users = sorted(
                premium_users,
                key=lambda x: datetime.fromisoformat(x["added_at"]),
                reverse=True
            )[:20]
            
            history_text = (
                f"<blockquote expandable>📜 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙃𝙞𝙨𝙩𝙤𝙧𝙮</blockquote>\n\n"
                f"<b>Recent Additions (Last 20):</b>\n\n"
            )
            
            for idx, user in enumerate(sorted_users, 1):
                added_at = datetime.fromisoformat(user["added_at"]).strftime('%d %b %y, %I:%M %p')
                duration = format_duration_display(user["duration_seconds"])
                
                history_text += (
                    f"<b>{idx}.</b> 👤 <code>{user['user_id']}</code>\n"
                    f"   📅 {added_at}\n"
                    f"   ⏰ {duration}\n"
                    f"   👨‍💼 By: <code>{user['added_by']}</code>\n\n"
                )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 View Stats", callback_data="refresh_stats")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_history")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
        
        await query.edit_message_text(history_text, reply_markup=keyboard)
        await query.answer("History refreshed! ✅")
        
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)


@Client.on_callback_query(filters.regex(r'^export_premium$'))
async def export_premium_callback(client: Client, query: CallbackQuery):
    """Export premium data via callback"""
    
    if not await is_admin(0, 0, query.from_user.id):
        return await query.answer("⛔ Only admins can do this!", show_alert=True)
    
    await query.answer("Generating export file... ⏳")
    
    try:
        premium_users = await PremiumManager.get_all_premium_users()
        
        if not premium_users:
            return await query.answer("No premium users to export!", show_alert=True)
        
        # Create export text
        export_text = "=" * 50 + "\n"
        export_text += "PREMIUM USERS EXPORT\n"
        export_text += f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
        export_text += f"Total Users: {len(premium_users)}\n"
        export_text += "=" * 50 + "\n\n"
        
        for idx, user in enumerate(premium_users, 1):
            time_left = PremiumManager.format_time_remaining(user["days_left"], user["hours_left"])
            expiry = user["expiry_date"].strftime('%d %b %Y, %I:%M %p')
            added_at = datetime.fromisoformat(user["added_at"]).strftime('%d %b %Y, %I:%M %p')
            duration = format_duration_display(user["duration_seconds"])
            
            export_text += f"{idx}. USER ID: {user['user_id']}\n"
            export_text += f"   Time Left: {time_left}\n"
            export_text += f"   Expires: {expiry}\n"
            export_text += f"   Added: {added_at}\n"
            export_text += f"   Added By: {user['added_by']}\n"
            export_text += f"   Duration: {duration}\n"
            export_text += "-" * 50 + "\n\n"
        
        # Save to file
        filename = f"premium_users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(export_text)
        
        # Send file
        await client.send_document(
            chat_id=query.from_user.id,
            document=filename,
            caption=(
                f"<b>📊 Premium Users Export</b>\n\n"
                f"👥 Total: <code>{len(premium_users)}</code>\n"
                f"📅 Generated: <code>{datetime.now().strftime('%d %b %Y, %I:%M %p')}</code>"
            )
        )
        
        # Delete file
        import os
        os.remove(filename)
        
        await query.answer("Export sent! ✅")
        
    except Exception as e:
        logging.error(f"Export error: {e}")
        await query.answer(f"Export failed: {str(e)}", show_alert=True)


# ==================== Help Command ====================

@Client.on_message(filters.command('premiumhelp') & filters.private)
async def premium_help_command(client: Client, message: Message):
    """Show all premium commands"""
    
    is_user_admin = await is_admin(0, 0, message.from_user.id)
    
    if is_user_admin:
        help_text = (
            "<blockquote expandable>📚 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝘾𝙤𝙢𝙢𝙖𝙣𝙙𝙨</blockquote>\n\n"
            "<b>👑 Admin Commands:</b>\n\n"
            "<b>➤ /addpremium</b> <code>user_id duration</code>\n"
            "<i>Add premium to a user</i>\n\n"
            "<b>➤ /addpremiumlist</b> <code>id1,id2,id3 duration</code>\n"
            "<i>Add premium to multiple users</i>\n\n"
            "<b>➤ /extendpremium</b> <code>user_id duration</code>\n"
            "<i>Extend existing premium</i>\n\n"
            "<b>➤ /removepremium</b> <code>user_id</code>\n"
            "<i>Remove premium from user</i>\n\n"
            "<b>➤ /checkpremium</b> <code>[user_id]</code>\n"
            "<i>Check premium status</i>\n\n"
            "<b>➤ /searchpremium</b> <code>user_id</code>\n"
            "<i>Search and manage premium user</i>\n\n"
            "<b>➤ /listpremium</b>\n"
            "<i>View all premium users</i>\n\n"
            "<b>➤ /premstats</b>\n"
            "<i>View premium statistics</i>\n\n"
            "<b>➤ /premiumhistory</b>\n"
            "<i>View recent additions</i>\n\n"
            "<b>➤ /exportpremium</b>\n"
            "<i>Export data to file</i>\n\n"
            "<b>👤 User Commands:</b>\n\n"
            "<b>➤ /mypremium</b>\n"
            "<i>Check your premium status</i>\n\n"
            "<b>⏰ Duration Formats:</b>\n"
            "<code>30s</code> = 30 seconds\n"
            "<code>5m</code> = 5 minutes\n"
            "<code>2h</code> = 2 hours\n"
            "<code>7d</code> = 7 days\n"
            "<code>3w</code> = 3 weeks\n"
            "<code>2mo</code> = 2 months\n"
            "<code>1y</code> = 1 year"
        )
    else:
        help_text = (
            "<blockquote expandable>📚 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝘾𝙤𝙢𝙢𝙖𝙣𝙙𝙨</blockquote>\n\n"
            "<b>👤 Available Commands:</b>\n\n"
            "<b>➤ /mypremium</b>\n"
            "<i>Check your premium status</i>\n\n"
            "<b>💎 Premium Benefits:</b>\n"
            "• 🚫 No ads or verification\n"
            "• ⚡ Direct download links\n"
            "• 🎯 Priority support\n"
            "• 🔓 Unlimited access\n\n"
            "<i>Contact admin to get premium!</i>"
        )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Get Premium", callback_data="prem")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])
    
    await message.reply_text(help_text, reply_markup=keyboard)


# ==================== Startup Hook ====================

async def initialize_premium_system():
    """Initialize premium system on bot startup"""
    try:
        logging.info("🔧 Initializing Premium System...")
        
        # Verify database connection
        premium_set = await PremiumManager._get_premium_set()
        user_count = len(premium_set)
        
        logging.info(f"✅ Premium System Initialized - {user_count} active users")
        
        # Start monitoring tasks
        start_premium_monitors()
        
        logging.info("✅ Premium monitors started successfully")
        
    except Exception as e:
        logging.error(f"❌ Failed to initialize premium system: {e}")


# ==================== Export Functions ====================

__all__ = [
    'PremiumManager',
    'is_premium_user',
    'start_premium_monitors',
    'initialize_premium_system',
    'prem'
]


# ==================== Auto-Initialize on Import ====================
# Uncomment the line below to auto-start monitors when module is imported
# asyncio.create_task(initialize_premium_system())
