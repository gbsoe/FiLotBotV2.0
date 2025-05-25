"""
Main Telegram bot implementation.
Handles user interactions, commands, and callback queries.
"""

import asyncio
from datetime import datetime
from typing import Optional
from loguru import logger

from config import Config
from utils.database import DatabaseManager
from utils.filot_client import FiLotClient
from utils.risk_manager import RiskManager
from handlers.user_commands import UserCommandHandlers
from handlers.callbacks import CallbackHandlers
from telegram.ext import Application

class TelegramBot:
    """
    Main Telegram bot class that coordinates all bot functionality.
    """
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.risk_manager = RiskManager(db_manager, config)
        
        # Initialize handlers
        self.user_handlers = UserCommandHandlers(config, db_manager, self.risk_manager)
        self.callback_handlers = CallbackHandlers(config, db_manager, self.risk_manager)
        
        logger.info("Telegram bot initialized")
    
    async def register_handlers(self, application: Application):
        """
        Register all command and callback handlers with the Telegram application.
        
        Args:
            application: Telegram Application instance
        """
        try:
            # Command handlers
            application.add_handler(
                CommandHandler("start", self.user_handlers.start_command)
            )
            application.add_handler(
                CommandHandler("help", self.user_handlers.help_command)
            )
            application.add_handler(
                CommandHandler("invest", self.user_handlers.invest_command)
            )
            application.add_handler(
                CommandHandler("pools", self.user_handlers.pools_command)
            )
            application.add_handler(
                CommandHandler("subscribe", self.user_handlers.subscribe_command)
            )
            application.add_handler(
                CommandHandler("unsubscribe", self.user_handlers.unsubscribe_command)
            )
            application.add_handler(
                CommandHandler("settings", self.user_handlers.settings_command)
            )
            application.add_handler(
                CommandHandler("report", self.user_handlers.report_command)
            )
            application.add_handler(
                CommandHandler("balance", self.user_handlers.balance_command)
            )
            application.add_handler(
                CommandHandler("status", self.user_handlers.status_command)
            )
            
            # Callback query handlers
            application.add_handler(
                CallbackQueryHandler(self.callback_handlers.handle_callback)
            )
            
            # Error handler
            application.add_error_handler(self._error_handler)
            
            logger.info("All handlers registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to register handlers: {e}")
            raise
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Global error handler for the bot.
        
        Args:
            update: Telegram update that caused the error
            context: Telegram context containing error information
        """
        logger.error(f"Bot error: {context.error}")
        
        # Try to notify the user if possible
        if update and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ An error occurred while processing your request. Please try again later."
                )
            except Exception as e:
                logger.error(f"Failed to send error message to user: {e}")
    
    async def send_notification(self, user_id: int, message: str, 
                              reply_markup=None) -> bool:
        """
        Send a notification message to a specific user.
        
        Args:
            user_id: Telegram user ID
            message: Message to send
            reply_markup: Optional inline keyboard
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            # This would need access to the bot instance
            # For now, this is a placeholder that would be called from the agent
            logger.info(f"Notification to user {user_id}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")
            return False
    
    async def broadcast_message(self, message: str, user_ids: Optional[list] = None) -> int:
        """
        Broadcast a message to multiple users.
        
        Args:
            message: Message to broadcast
            user_ids: List of user IDs (if None, sends to all active users)
            
        Returns:
            Number of users who received the message
        """
        try:
            if user_ids is None:
                # Get all active users from database
                # This would need to be implemented in DatabaseManager
                user_ids = []
            
            sent_count = 0
            for user_id in user_ids:
                if await self.send_notification(user_id, message):
                    sent_count += 1
                    
                # Add small delay to avoid rate limiting
                await asyncio.sleep(0.1)
            
            logger.info(f"Broadcast sent to {sent_count}/{len(user_ids)} users")
            return sent_count
            
        except Exception as e:
            logger.error(f"Failed to broadcast message: {e}")
            return 0
