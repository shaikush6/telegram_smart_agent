"""
main_bot.py - Main entry point for the Silo Telegram Bot
"""

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import Config
import database
from handlers import (
    start_command,
    help_command,
    recent_command,
    search_command,
    stats_command,
    export_command,
    archive_command,
    handle_message
)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Run the Silo bot."""
    # Create the Application and pass it your bot's token.
    config = Config()
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("recent", recent_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("archive", archive_command))

    # Register message handler for URLs and natural language queries
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting Silo bot...")
    application.run_polling()

if __name__ == '__main__':
    # Create database tables if they don't exist
    try:
        database.create_tables()
        logger.info("Database tables created or already exist.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        # Depending on the setup, you might want to exit here if the DB is essential

    main()