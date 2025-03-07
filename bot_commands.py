from datetime import datetime

from config import logger
from handlers import process_new_calls, get_period_calls, create_test_audio_file
from utils import (
    prevent_concurrent_requests,
    user_locks,
    user_locks_mutex,
    send_progress_update,
)


def register_commands(bot):
    """
    Register command handlers for the bot

    Args:
        bot: Telegram bot instance
    """

    # Command handler for manually checking new calls
    @bot.message_handler(commands=["check"])
    @prevent_concurrent_requests
    def check_command(message):
        if message.chat.type == "private":
            bot.reply_to(message, "Checking for new calls...")
            count = process_new_calls(bot)
            bot.send_message(
                message.chat.id, f"Check completed! Processed {count} calls."
            )

    # Command to get today's calls
    @bot.message_handler(commands=['today'])
    @prevent_concurrent_requests
    def today_calls_command(message):
        if message.chat.type == 'private':
            # Send initial status with better formatting
            status_msg = bot.send_message(
                message.chat.id, 
                "<b>Processing: Today's Calls</b>\n\n⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪ 0%\n\n<i>Initializing...</i>",
                parse_mode='HTML'
            )
            
            # Calculate today's start and end timestamps
            today_start = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
            today_end = int(datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999).timestamp())
            
            # Update with more informative progress steps
            send_progress_update(message.chat.id, status_msg.message_id, "Fetching Today's Calls", bot, 0.2)
            
            get_period_calls(bot, message.chat.id, today_start, today_end, "today", status_msg)
    # Command to get current month's calls
    @bot.message_handler(commands=["month"])
    @prevent_concurrent_requests
    def month_calls_command(message):
        if message.chat.type == "private":
            status_msg = bot.reply_to(message, "Fetching this month's calls...")

            # Calculate current month's start and end timestamps
            now = datetime.now()
            month_start = int(datetime(now.year, now.month, 1).timestamp())
            if now.month == 12:
                month_end = int(datetime(now.year + 1, 1, 1).timestamp()) - 1
            else:
                month_end = int(datetime(now.year, now.month + 1, 1).timestamp()) - 1
            send_progress_update(
                message.chat.id, status_msg.message_id, "Authenticating...", bot, 0.2
            )
            get_period_calls(
                bot, message.chat.id, month_start, month_end, "this month", status_msg
            )

    # Command to get yesterday's calls
    @bot.message_handler(commands=["yesterday"])
    @prevent_concurrent_requests
    def yesterday_calls_command(message):
        if message.chat.type == "private":
            bot.reply_to(message, "Fetching yesterday's calls...")

            # Calculate yesterday's start and end timestamps
            now = datetime.now()
            yesterday = (
                datetime(now.year, now.month, now.day).timestamp() - 86400
            )  # 24 hours in seconds
            yesterday_start = int(
                datetime.fromtimestamp(yesterday)
                .replace(hour=0, minute=0, second=0)
                .timestamp()
            )
            yesterday_end = int(
                datetime.fromtimestamp(yesterday)
                .replace(hour=23, minute=59, second=59)
                .timestamp()
            )

            get_period_calls(
                bot, message.chat.id, yesterday_start, yesterday_end, "yesterday"
            )

    # Command to get last week's calls
    @bot.message_handler(commands=["week"])
    @prevent_concurrent_requests
    def week_calls_command(message):
        if message.chat.type == "private":
            bot.reply_to(message, "Fetching this week's calls...")

            # Calculate current week's start and end timestamps
            now = datetime.now()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            weekday = today.weekday()  # Monday is 0, Sunday is 6
            week_start = int(
                (today.timestamp() - weekday * 86400)
            )  # Start of week (Monday)
            week_end = int(now.timestamp())  # Current time

            get_period_calls(bot, message.chat.id, week_start, week_end, "this week")

    # Setup webhook
    @bot.message_handler(commands=["setup"])
    @prevent_concurrent_requests
    def setup_webhook(message):
        if message.chat.type == "private":
            try:
                from main import setup_webhook as setup_webhook_func

                setup_webhook_func(bot)
                bot.reply_to(message, "Webhook setup completed!")
            except Exception as e:
                logger.error(f"Error setting up webhook: {e}", exc_info=True)
                bot.reply_to(message, f"Error setting up webhook: {e}")

    # Start command
    @bot.message_handler(commands=["start"])
    @prevent_concurrent_requests
    def start_command(message):
        bot.send_message(
            message.chat.id,
            "👋 <b>Welcome to OnlinePBX Call Notification Bot!</b>\n\n"
            "<b>Commands:</b>\n"
            "/check - Check for new calls manually\n"
            "/today - Get all of today's calls\n"
            "/yesterday - Get all of yesterday's calls\n"
            "/week - Get all calls for current week\n"
            "/month - Get all calls for current month\n"
            "/cancel - Cancel current operation\n"
            "/stats - Get call statistics\n",
            parse_mode="HTML",
        )

    @bot.message_handler(commands=["cancel"])
    def cancel_command(message):
        user_id = message.from_user.id
        with user_locks_mutex:
            if user_id in user_locks and user_locks[user_id]:
                user_locks[user_id] = False
                bot.reply_to(message, "✅ Operation canceled.")
            else:
                bot.reply_to(message, "There's no active operation to cancel.")

    # Test command for audio sending
    # Stats command
    @bot.message_handler(commands=["stats"])
    @prevent_concurrent_requests
    def stats_command(message):
        if message.chat.type == "private":
            try:
                bot.reply_to(message, "Fetching call statistics...")

                # Get calls for different periods
                now = datetime.now()

                # Today
                today_start = int(
                    now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                )

                # This month
                month_start = int(datetime(now.year, now.month, 1).timestamp())

                # Last 24 hours
                day_ago = int(now.timestamp() - 86400)

                # Get stats
                from api import OnlinePBXAPI

                api = OnlinePBXAPI()
                if not api.authenticate():
                    bot.send_message(
                        message.chat.id, "Failed to authenticate with OnlinePBX API"
                    )
                    return

                # Get call details for different periods
                today_calls = (
                    api.get_call_details(today_start, int(now.timestamp())) or []
                )
                monthly_calls = (
                    api.get_call_details(month_start, int(now.timestamp())) or []
                )
                recent_calls = api.get_call_details(day_ago, int(now.timestamp())) or []

                # Calculate stats
                total_today = len(today_calls)
                total_month = len(monthly_calls)
                total_recent = len(recent_calls)

                # Count call types for today
                inbound_today = sum(
                    1 for call in today_calls if call.get("accountcode") == "inbound"
                )
                outbound_today = sum(
                    1 for call in today_calls if call.get("accountcode") == "outbound"
                )

                # Count contacted calls
                contacted_today = sum(
                    1 for call in today_calls if call.get("contacted", False)
                )
                contacted_month = sum(
                    1 for call in monthly_calls if call.get("contacted", False)
                )

                # Calculate average durations
                if today_calls:
                    avg_duration_today = sum(
                        call.get("duration", 0) for call in today_calls
                    ) / len(today_calls)
                    avg_duration_today_mins = round(avg_duration_today / 60, 1)
                else:
                    avg_duration_today_mins = 0

                if monthly_calls:
                    avg_duration_month = sum(
                        call.get("duration", 0) for call in monthly_calls
                    ) / len(monthly_calls)
                    avg_duration_month_mins = round(avg_duration_month / 60, 1)
                else:
                    avg_duration_month_mins = 0

                # Send statistics
                stats_message = (
                    "📊 <b>Call Statistics</b>\n\n"
                    f"<b>Today:</b>\n"
                    f"- Total calls: {total_today}\n"
                    f"- Inbound calls: {inbound_today}\n"
                    f"- Outbound calls: {outbound_today}\n"
                    f"- Contacted: {contacted_today}\n"
                    f"- Average duration: {avg_duration_today_mins} minutes\n\n"
                    f"<b>This month:</b>\n"
                    f"- Total calls: {total_month}\n"
                    f"- Contacted: {contacted_month}\n"
                    f"- Average duration: {avg_duration_month_mins} minutes\n\n"
                    f"<b>Last 24 hours:</b>\n"
                    f"- Total calls: {total_recent}\n\n"
                    f"<i>Statistics as of {now.strftime('%Y-%m-%d %H:%M')}</i>"
                )

                bot.send_message(message.chat.id, stats_message, parse_mode="HTML")

            except Exception as e:
                logger.error(f"Error fetching statistics: {e}", exc_info=True)
                bot.reply_to(message, f"Error fetching statistics: {e}")
    @bot.callback_query_handler(func=lambda call: call.data.startswith('cancel_'))
    def cancel_callback(call):
        user_id = int(call.data.split('_')[1])
        calling_user_id = call.from_user.id
        
        # Only the same user can cancel their operation
        if calling_user_id != user_id:
            bot.answer_callback_query(call.id, "You can only cancel your own operations")
            return
            
        with user_locks_mutex:
            if user_id in user_locks and user_locks[user_id]:
                user_locks[user_id] = False
                bot.edit_message_text(
                    "✅ Operation canceled.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
            else:
                bot.answer_callback_query(call.id, "No active operation to cancel")