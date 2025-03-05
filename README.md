# OnlinePBX Call Notification Bot

This Telegram bot fetches call data from OnlinePBX APIs and forwards it to a Telegram channel/group with call details and recordings.

## Features

- Real-time call notifications
- Sends audio recordings of calls when available
- Displays formatted call information (caller, duration, etc.)
- Supports webhook and polling modes
- Commands for retrieving calls by time period (today, yesterday, month, etc.)
- Call statistics
- Robust error handling with fallback to text-only notifications
- Detailed logging

## Installation

1. Clone this repository
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Update the configuration in `config.py` (bot token, channel ID, webhook settings)
4. Run the bot:
   ```
   python main.py
   ```

## Configuration

Edit `config.py` to set:

- `TELEGRAM_BOT_TOKEN`: Your bot token from @BotFather
- `TELEGRAM_CHANNEL_ID`: ID of the channel where calls will be sent
- `WEBHOOK_HOST`: Your public domain/IP (with ngrok or similar)
- `AUTH_KEY`: Your OnlinePBX authentication key

## Usage

### Commands

- `/start` - Show help message
- `/check` - Check for new calls manually
- `/today` - Get all of today's calls
- `/yesterday` - Get all of yesterday's calls
- `/week` - Get all calls for current week
- `/month` - Get all calls for current month
- `/stats` - Get call statistics
- `/setup` - Set up webhook for real-time notifications
- `/test` - Test audio file sending

## Project Structure

- `main.py` - Main script, handles webhook setup and polling loop
- `config.py` - Configuration settings
- `api.py` - OnlinePBX API client
- `utils.py` - Utility functions for file handling and message formatting
- `handlers.py` - Core logic for processing and sending calls
- `bot_commands.py` - Telegram bot command handlers

## Requirements

- Python 3.7+
- telebot
- Flask
- requests

## Troubleshooting

- If the bot cannot send audio files, run the `/test` command to check permissions
- Check the log file (`logs/bot.log`) for detailed error information
- Make sure the bot is an admin in the target channel with permission to post media