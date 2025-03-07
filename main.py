import telebot
import time
from flask import Flask, request

from config import (
    TELEGRAM_BOT_TOKEN,
    WEBHOOK_URL_BASE,
    WEBHOOK_URL_PATH,
    WEBHOOK_LISTEN,
    WEBHOOK_PORT,
    logger,
)
from handlers import process_new_calls
from bot_commands import register_commands
from utils import prevent_concurrent_requests, user_locks, user_locks_mutex

# Initialize bot and Flask app
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

# Register bot commands
register_commands(bot)


# Webhook handler
@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.stream.read().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'OK'


def setup_webhook(bot_instance=None):
    """
    Set up the webhook for the bot

    Args:
        bot_instance: Optional bot instance (defaults to global bot)
    """
    bot_to_setup = bot_instance or bot
    bot_to_setup.remove_webhook()
    bot_to_setup.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
    logger.info(f"Webhook set to {WEBHOOK_URL_BASE + WEBHOOK_URL_PATH}")
    return True


if __name__ == "__main__":
    try:
        logger.info("Starting OnlinePBX Call Notification Bot")

        # Process any existing calls that might have been missed
        logger.info("Processing existing calls...")
        process_new_calls(bot)

        # Try to set up webhook
        try:
            setup_webhook()

            # Start Flask server
            logger.info(f"Starting Flask server on {WEBHOOK_LISTEN}:{WEBHOOK_PORT}")
            app.run(host=WEBHOOK_LISTEN, port=WEBHOOK_PORT)
        except Exception as e:
            logger.error(f"Error starting webhook: {e}", exc_info=True)

            # Fall back to polling mode
            logger.info("Falling back to polling mode")
            bot.remove_webhook()

            # Schedule regular checks
            logger.info("Starting regular polling loop")
            while True:
                try:
                    # Check for new calls
                    process_new_calls(bot)
                except Exception as e:
                    logger.error(f"Error in main loop: {e}", exc_info=True)

                # Wait before checking again
                logger.info("Sleeping for 5 minutes before next check")
                time.sleep(300)
    except Exception as e:
        logger.critical(f"Critical error in main function: {e}", exc_info=True)
