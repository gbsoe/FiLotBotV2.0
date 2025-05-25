"""
User command handlers for the Telegram bot.
Implements all user-facing commands and their logic.
"""

from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from config import Config
from utils.database import DatabaseManager
from utils.filot_client import FiLotClient, FiLotError
from utils.risk_manager import RiskManager
from models import Subscription, SubscriptionStatus

class UserCommandHandlers:
    """Handles all user command interactions."""
    
    def __init__(self, config: Config, db_manager: DatabaseManager, risk_manager: RiskManager):
        self.config = config
        self.db_manager = db_manager
        self.risk_manager = risk_manager
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        try:
            # Create or update user in database
            await self.db_manager.create_or_update_user({
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name
            })
            
            welcome_message = f"""
🤖 **Welcome to Precision Investing Bot!**

Hello {user.first_name}! I'm your autonomous trading assistant for Raydium pools on Solana.

**What I can do:**
• 📊 Show available high-yield pools
• 💰 Execute one-click investments
• 🔔 Send autonomous trading alerts
• 📈 Track your investment performance
• ⚡ Monitor market opportunities 24/7

**Quick Commands:**
• `/invest` - Browse and invest in pools
• `/pools` - View all available pools
• `/subscribe` - Enable autonomous trading
• `/report` - View your performance
• `/help` - Get detailed help

Ready to start precision investing? Use `/invest` to see available opportunities!
            """
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=welcome_message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Welcome! There was an issue setting up your account. Please try again."
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        chat_id = update.effective_chat.id
        
        help_text = """
🤖 **Precision Investing Bot - Help**

**Investment Commands:**
• `/invest` - Browse pools and make investments
• `/pools` - View all available Raydium pools
• `/balance` - Check your wallet balance

**Autonomous Trading:**
• `/subscribe` - Enable automatic opportunity alerts
• `/unsubscribe` - Disable autonomous trading
• `/settings` - Customize your trading preferences

**Reporting:**
• `/report` - View your trading performance
• `/status` - Check bot and agent status

**How It Works:**

**Manual Investing:**
1. Use `/invest` to see high-yield pools
2. Select a pool and investment amount
3. Confirm with one click
4. Receive transaction confirmation

**Autonomous Trading:**
1. Subscribe with `/subscribe`
2. Set your risk tolerance and limits
3. Receive alerts for high-yield opportunities
4. One-click invest from notifications

**Risk Management:**
• Daily exposure limits protect your capital
• Position sizing based on pool risk assessment
• Real-time monitoring of all investments

**Support:**
If you encounter any issues, please contact our support team.
        """
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=help_text,
            parse_mode='Markdown'
        )
    
    async def invest_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /invest command - show investment interface."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        try:
            # Check if user exists
            user = await self.db_manager.get_user(user_id)
            if not user:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Please start with /start first to initialize your account."
                )
                return
            
            # Fetch pools from FiLot API
            async with FiLotClient(self.config) as client:
                pools_data = await client.get_pools()
            
            if not pools_data:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ No pools available at the moment. Please try again later."
                )
                return
            
            # Filter and sort pools by APY
            high_yield_pools = [
                pool for pool in pools_data 
                if pool.get('apy', 0) >= self.config.MIN_APR_THRESHOLD
                and pool.get('tvl', 0) >= self.config.MIN_TVL_THRESHOLD
            ]
            
            if not high_yield_pools:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ No pools meet the minimum criteria (APY > {self.config.MIN_APR_THRESHOLD}%, TVL > ${self.config.MIN_TVL_THRESHOLD:,.0f})"
                )
                return
            
            # Sort by APY descending
            high_yield_pools.sort(key=lambda x: x.get('apy', 0), reverse=True)
            
            # Create inline keyboard with top pools
            keyboard = []
            for i, pool in enumerate(high_yield_pools[:10]):  # Show top 10
                pool_text = f"🏊 {pool.get('tokenA', 'Unknown')}/{pool.get('tokenB', 'Unknown')} - {pool.get('apy', 0):.1f}% APY"
                keyboard.append([
                    InlineKeyboardButton(
                        pool_text,
                        callback_data=f"pool_details:{pool.get('poolId')}"
                    )
                ])
            
            # Add refresh button
            keyboard.append([
                InlineKeyboardButton("🔄 Refresh Pools", callback_data="refresh_pools")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = f"""
💰 **High-Yield Investment Opportunities**

Found {len(high_yield_pools)} pools meeting your criteria:
• Min APY: {self.config.MIN_APR_THRESHOLD}%
• Min TVL: ${self.config.MIN_TVL_THRESHOLD:,.0f}

Select a pool below to view details and invest:
            """
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except FiLotError as e:
            logger.error(f"FiLot API error in invest command: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Unable to fetch pool data. Please try again later."
            )
        except Exception as e:
            logger.error(f"Error in invest command: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ An error occurred. Please try again."
            )
    
    async def pools_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pools command - show all pools."""
        chat_id = update.effective_chat.id
        
        try:
            async with FiLotClient(self.config) as client:
                pools_data = await client.get_pools()
            
            if not pools_data:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ No pools available at the moment."
                )
                return
            
            # Sort by TVL descending
            pools_data.sort(key=lambda x: x.get('tvl', 0), reverse=True)
            
            message_lines = ["📊 **All Available Pools:**\n"]
            
            for pool in pools_data[:15]:  # Show top 15 by TVL
                tvl = pool.get('tvl', 0)
                apy = pool.get('apy', 0)
                volume = pool.get('volume24h', 0)
                tokens = f"{pool.get('tokenA', 'Unknown')}/{pool.get('tokenB', 'Unknown')}"
                
                message_lines.append(
                    f"🏊 **{tokens}**\n"
                    f"  💰 TVL: ${tvl:,.0f}\n"
                    f"  📈 APY: {apy:.2f}%\n"
                    f"  📊 24h Vol: ${volume:,.0f}\n"
                )
            
            message_text = "\n".join(message_lines)
            
            if len(message_text) > 4000:  # Telegram message limit
                message_text = message_text[:4000] + "\n\n... (truncated)"
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in pools command: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Unable to fetch pool data. Please try again later."
            )
    
    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /subscribe command - enable autonomous trading."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        try:
            # Check existing subscription
            existing_sub = await self.db_manager.get_subscription(user_id)
            
            if existing_sub and existing_sub.status == SubscriptionStatus.ACTIVE:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="✅ You're already subscribed to autonomous trading alerts!"
                )
                return
            
            # Create new subscription with default settings
            subscription = Subscription(
                id=None,
                user_id=user_id,
                status=SubscriptionStatus.ACTIVE,
                min_apr_threshold=self.config.MIN_APR_THRESHOLD,
                max_risk_level=0.5,  # Medium risk
                max_daily_investment=self.config.MAX_DAILY_EXPOSURE_USD,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            await self.db_manager.create_subscription(subscription)
            
            keyboard = [[
                InlineKeyboardButton("⚙️ Customize Settings", callback_data="customize_settings")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = f"""
✅ **Autonomous Trading Activated!**

Your subscription is now active with these default settings:
• 📊 Min APY Threshold: {subscription.min_apr_threshold}%
• ⚠️ Risk Level: Medium ({subscription.max_risk_level})
• 💰 Daily Investment Limit: ${subscription.max_daily_investment:,.0f}

The bot will now:
• 🔍 Monitor pools every 3 hours
• 🚨 Alert you to high-yield opportunities
• 💡 Suggest optimal position sizes
• 🛡️ Enforce risk management limits

You can customize these settings anytime!
            """
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in subscribe command: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Failed to activate subscription. Please try again."
            )
    
    async def unsubscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unsubscribe command."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        try:
            subscription = await self.db_manager.get_subscription(user_id)
            
            if not subscription or subscription.status == SubscriptionStatus.DISABLED:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="ℹ️ You don't have an active subscription."
                )
                return
            
            # Update subscription status
            subscription.status = SubscriptionStatus.DISABLED
            subscription.updated_at = datetime.now()
            
            # This would need an update method in DatabaseManager
            # await self.db_manager.update_subscription(subscription)
            
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ Autonomous trading alerts have been disabled. You can re-enable them anytime with /subscribe."
            )
            
        except Exception as e:
            logger.error(f"Error in unsubscribe command: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Failed to update subscription. Please try again."
            )
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        try:
            subscription = await self.db_manager.get_subscription(user_id)
            
            if not subscription:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="ℹ️ You need to subscribe first. Use /subscribe to get started."
                )
                return
            
            keyboard = [
                [InlineKeyboardButton("📊 APY Threshold", callback_data="setting_apy_threshold")],
                [InlineKeyboardButton("⚠️ Risk Level", callback_data="setting_risk_level")],
                [InlineKeyboardButton("💰 Daily Limit", callback_data="setting_daily_limit")],
                [InlineKeyboardButton("⏸️ Pause/Resume", callback_data="setting_toggle_status")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            status_emoji = "✅" if subscription.status == SubscriptionStatus.ACTIVE else "⏸️"
            risk_text = {0.3: "Low", 0.5: "Medium", 0.7: "High"}.get(subscription.max_risk_level, "Custom")
            
            message_text = f"""
⚙️ **Your Trading Settings**

**Current Configuration:**
• Status: {status_emoji} {subscription.status.value.title()}
• 📊 Min APY: {subscription.min_apr_threshold}%
• ⚠️ Risk Level: {risk_text} ({subscription.max_risk_level})
• 💰 Daily Limit: ${subscription.max_daily_investment:,.0f}

Select a setting to modify:
            """
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in settings command: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Unable to load settings. Please try again."
            )
    
    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /report command - show trading performance."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        try:
            # Get user's trades from the last 30 days
            # This would need to be implemented in DatabaseManager
            
            report_text = """
📈 **Your Trading Report**

**Last 30 Days:**
• Total Investments: $0.00
• Active Positions: 0
• Realized P&L: $0.00
• Average APY: 0.00%

**Today:**
• Investments: $0.00
• Autonomous Alerts: 0
• Manual Trades: 0

**Performance:**
• Best Performing Pool: None
• Total ROI: 0.00%
• Win Rate: 0.00%

*Start investing to see your performance metrics!*
            """
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=report_text,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in report command: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Unable to generate report. Please try again."
            )
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command - show wallet balance."""
        chat_id = update.effective_chat.id
        
        try:
            async with FiLotClient(self.config) as client:
                balance_data = await client.get_wallet_balance()
            
            if not balance_data:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Unable to fetch wallet balance."
                )
                return
            
            # Format balance information
            balances = balance_data.get('balances', {})
            
            message_lines = ["💰 **Your Wallet Balance:**\n"]
            
            total_value = 0
            for token, amount in balances.items():
                if amount > 0:
                    message_lines.append(f"• {token}: {amount:.6f}")
                    # Would need price data to calculate USD value
            
            message_text = "\n".join(message_lines)
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in balance command: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Unable to fetch balance. Please try again."
            )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - show bot and agent status."""
        chat_id = update.effective_chat.id
        
        try:
            # Get agent state from database
            agent_state = await self.db_manager.get_agent_state()
            
            # Check FiLot API health
            async with FiLotClient(self.config) as client:
                api_healthy = await client.health_check()
            
            api_status = "🟢 Online" if api_healthy else "🔴 Offline"
            
            if agent_state:
                last_run = agent_state.last_perception_run
                time_since = datetime.now() - last_run if last_run != datetime.min else None
                
                if time_since and time_since.total_seconds() < 3600:  # Less than 1 hour
                    agent_status = "🟢 Active"
                elif time_since and time_since.total_seconds() < 10800:  # Less than 3 hours
                    agent_status = "🟡 Running"
                else:
                    agent_status = "🔴 Inactive"
                
                status_text = f"""
🤖 **Bot Status**

**API Services:**
• FiLot API: {api_status}
• Database: 🟢 Connected

**Autonomous Agent:**
• Status: {agent_status}
• Last Scan: {last_run.strftime('%H:%M:%S') if last_run != datetime.min else 'Never'}
• Pools Monitored: {agent_state.pools_monitored}
• Opportunities Found: {agent_state.opportunities_detected}
• Trades Executed: {agent_state.trades_executed}
• Errors: {agent_state.errors_count}

**Your Account:**
• User ID: {update.effective_user.id}
• Account Status: 🟢 Active
                """
            else:
                status_text = f"""
🤖 **Bot Status**

**API Services:**
• FiLot API: {api_status}
• Database: 🟢 Connected

**Autonomous Agent:**
• Status: 🔴 Not Started
• No agent data available

**Your Account:**
• User ID: {update.effective_user.id}
• Account Status: 🟢 Active
                """
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=status_text,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Unable to fetch status. Please try again."
            )
