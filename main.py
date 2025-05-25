"""
Main entry point for the Precision Investing Telegram Bot.
Combines user-driven manual trading with autonomous agent capabilities.
"""

import asyncio
import os
from loguru import logger
from config import Config
from bot import TelegramBot
from agent import AutonomousAgent
from utils.database import DatabaseManager

async def main():
    """
    Initialize and run the bot with both manual and autonomous capabilities.
    """
    # Configure logging
    logger.add("logs/bot_{time}.log", rotation="1 day", retention="30 days")
    logger.info("Starting Precision Investing Bot...")
    
    # Load configuration
    config = Config()
    
    # Initialize database
    db_manager = DatabaseManager(config.DATABASE_PATH)
    await db_manager.initialize()
    
    # Initialize Telegram bot
    telegram_bot = TelegramBot(config, db_manager)
    
    # Initialize autonomous agent
    autonomous_agent = AutonomousAgent(config, db_manager, telegram_bot)
    
    # Create Telegram application
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()
    
    # Register handlers
    await telegram_bot.register_handlers(application)
    
    # Start autonomous agent
    await autonomous_agent.start()
    
    try:
        # Start the bot
        logger.info("Bot is starting...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Keep the bot running
        logger.info("Bot is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
    finally:
        # Cleanup
        await autonomous_agent.stop()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
