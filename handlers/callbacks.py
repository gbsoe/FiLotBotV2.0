"""
Callback query handlers for the Telegram bot.
Handles all inline keyboard interactions and callbacks.
"""

from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from config import Config
from utils.database import DatabaseManager
from utils.filot_client import FiLotClient, FiLotError
from utils.risk_manager import RiskManager
from models import Trade, TradeStatus

class CallbackHandlers:
    """Handles all callback query interactions."""
    
    def __init__(self, config: Config, db_manager: DatabaseManager, risk_manager: RiskManager):
        self.config = config
        self.db_manager = db_manager
        self.risk_manager = risk_manager
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Main callback handler that routes to specific handlers based on callback data.
        """
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        try:
            if callback_data.startswith("pool_details:"):
                await self._handle_pool_details(query, context, callback_data)
            elif callback_data.startswith("invest_pool:"):
                await self._handle_invest_pool(query, context, callback_data)
            elif callback_data.startswith("confirm_invest:"):
                await self._handle_confirm_invest(query, context, callback_data)
            elif callback_data == "refresh_pools":
                await self._handle_refresh_pools(query, context)
            elif callback_data.startswith("setting_"):
                await self._handle_settings(query, context, callback_data)
            elif callback_data == "customize_settings":
                await self._handle_customize_settings(query, context)
            else:
                await query.edit_message_text("❌ Unknown action. Please try again.")
                
        except Exception as e:
            logger.error(f"Error in callback handler: {e}")
            await query.edit_message_text("❌ An error occurred. Please try again.")
    
    async def _handle_pool_details(self, query, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Handle pool details callback."""
        pool_id = callback_data.split(":")[1]
        
        try:
            async with FiLotClient(self.config) as client:
                pool_details = await client.get_pool_details(pool_id)
                pool_metrics = await client.get_pool_metrics(pool_id)
            
            # Extract pool information
            pool_data = pool_details.get('pool', {})
            tokens = f"{pool_data.get('tokenA', 'Unknown')}/{pool_data.get('tokenB', 'Unknown')}"
            tvl = pool_data.get('tvl', 0)
            apy = pool_data.get('apy', 0)
            volume_24h = pool_data.get('volume24h', 0)
            fee_rate = pool_data.get('feeRate', 0)
            
            # Calculate risk assessment
            from models import Pool
            pool_obj = Pool(
                pool_id=pool_id,
                token_a=pool_data.get('tokenA', ''),
                token_b=pool_data.get('tokenB', ''),
                tvl=tvl,
                volume_24h=volume_24h,
                apy=apy,
                fee_rate=fee_rate,
                last_updated=datetime.now()
            )
            
            risk_metrics = await self.risk_manager.assess_pool_risk(pool_obj)
            risk_level = {
                0.1: "🟢 Very Low",
                0.3: "🟡 Low", 
                0.5: "🟠 Medium",
                0.7: "🔴 High",
                1.0: "⚫ Very High"
            }
            
            # Find closest risk level
            risk_score = risk_metrics['overall_risk']
            risk_text = "🟠 Medium"
            for threshold, text in risk_level.items():
                if risk_score <= threshold:
                    risk_text = text
                    break
            
            # Calculate suggested position size
            suggested_amount = await self.risk_manager.calculate_position_size(
                query.from_user.id, pool_obj, max_risk_level=0.7
            )
            
            keyboard = []
            if suggested_amount and suggested_amount > 0:
                keyboard.append([
                    InlineKeyboardButton(
                        f"💰 Invest ${suggested_amount:.0f} (Suggested)",
                        callback_data=f"invest_pool:{pool_id}:{suggested_amount:.0f}"
                    )
                ])
                
                # Add custom amount options
                custom_amounts = [100, 250, 500, 1000]
                amount_row = []
                for amount in custom_amounts:
                    if amount != int(suggested_amount):
                        amount_row.append(
                            InlineKeyboardButton(
                                f"${amount}",
                                callback_data=f"invest_pool:{pool_id}:{amount}"
                            )
                        )
                        if len(amount_row) == 2:  # 2 buttons per row
                            keyboard.append(amount_row)
                            amount_row = []
                
                if amount_row:  # Add remaining buttons
                    keyboard.append(amount_row)
            else:
                keyboard.append([
                    InlineKeyboardButton(
                        "❌ Too Risky - Not Recommended",
                        callback_data="pool_too_risky"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("🔙 Back to Pools", callback_data="refresh_pools")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = f"""
🏊 **Pool Details: {tokens}**

**💰 Financial Metrics:**
• TVL: ${tvl:,.0f}
• APY: {apy:.2f}%
• 24h Volume: ${volume_24h:,.0f}
• Fee Rate: {fee_rate:.2f}%

**⚠️ Risk Assessment:**
• Overall Risk: {risk_text} ({risk_score:.2f})
• TVL Risk: {risk_metrics['tvl_risk']:.2f}
• Volume Risk: {risk_metrics['volume_risk']:.2f}
• APY Risk: {risk_metrics['apy_risk']:.2f}

**💡 Investment Recommendation:**
{f"Suggested amount: ${suggested_amount:.0f}" if suggested_amount else "❌ Pool too risky for investment"}

Select an investment amount below:
            """
            
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error fetching pool details: {e}")
            await query.edit_message_text("❌ Unable to fetch pool details. Please try again.")
    
    async def _handle_invest_pool(self, query, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Handle investment amount selection."""
        parts = callback_data.split(":")
        pool_id = parts[1]
        amount = float(parts[2])
        user_id = query.from_user.id
        
        try:
            # Get pool details for confirmation
            async with FiLotClient(self.config) as client:
                pool_details = await client.get_pool_details(pool_id)
            
            pool_data = pool_details.get('pool', {})
            tokens = f"{pool_data.get('tokenA', 'Unknown')}/{pool_data.get('tokenB', 'Unknown')}"
            apy = pool_data.get('apy', 0)
            
            # Perform risk checks
            can_trade, trade_reason = await self.risk_manager.should_execute_trade(
                user_id, 
                Pool(
                    pool_id=pool_id,
                    token_a=pool_data.get('tokenA', ''),
                    token_b=pool_data.get('tokenB', ''),
                    tvl=pool_data.get('tvl', 0),
                    volume_24h=pool_data.get('volume24h', 0),
                    apy=apy,
                    fee_rate=pool_data.get('feeRate', 0),
                    last_updated=datetime.now()
                ), 
                amount
            )
            
            if not can_trade:
                keyboard = [[
                    InlineKeyboardButton("🔙 Back to Pool", callback_data=f"pool_details:{pool_id}")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text=f"❌ **Investment Blocked**\n\n{trade_reason}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return
            
            # Get swap quote
            async with FiLotClient(self.config) as client:
                quote = await client.get_swap_quote(
                    input_token="USDC",  # Assuming USDC as input
                    output_token=pool_data.get('tokenA', ''),
                    amount=amount,
                    slippage=self.config.MAX_SLIPPAGE
                )
            
            expected_output = quote.get('expectedOutput', 0)
            price_impact = quote.get('priceImpact', 0)
            
            keyboard = [
                [InlineKeyboardButton(
                    "✅ Confirm Investment",
                    callback_data=f"confirm_invest:{pool_id}:{amount}"
                )],
                [InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=f"pool_details:{pool_id}"
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = f"""
💰 **Investment Confirmation**

**Pool:** {tokens}
**Amount:** ${amount:.2f} USDC
**Expected APY:** {apy:.2f}%

**Transaction Details:**
• Expected Output: {expected_output:.6f} {pool_data.get('tokenA', '')}
• Price Impact: {price_impact:.2f}%
• Max Slippage: {self.config.MAX_SLIPPAGE}%

**Risk Check:** ✅ {trade_reason}

⚠️ **Important:** This will execute a real transaction on Solana. Please confirm you want to proceed.
            """
            
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error preparing investment: {e}")
            await query.edit_message_text("❌ Unable to prepare investment. Please try again.")
    
    async def _handle_confirm_invest(self, query, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Handle investment confirmation and execution."""
        parts = callback_data.split(":")
        pool_id = parts[1]
        amount = float(parts[2])
        user_id = query.from_user.id
        
        try:
            # Create trade record
            trade = Trade(
                id=None,
                user_id=user_id,
                pool_id=pool_id,
                trade_type="manual",
                input_token="USDC",
                output_token="",  # Will be filled after execution
                input_amount=amount,
                output_amount=None,
                slippage=self.config.MAX_SLIPPAGE,
                transaction_hash=None,
                status=TradeStatus.PENDING,
                created_at=datetime.now(),
                executed_at=None,
                error_message=None
            )
            
            trade = await self.db_manager.create_trade(trade)
            
            # Show processing message
            await query.edit_message_text(
                "⏳ **Processing Investment...**\n\nPlease wait while we execute your trade on Solana.",
                parse_mode='Markdown'
            )
            
            # Execute the swap
            async with FiLotClient(self.config) as client:
                # Get pool details to determine output token
                pool_details = await client.get_pool_details(pool_id)
                pool_data = pool_details.get('pool', {})
                output_token = pool_data.get('tokenA', '')
                
                # Execute swap
                result = await client.execute_swap(
                    input_token="USDC",
                    output_token=output_token,
                    amount=amount,
                    slippage=self.config.MAX_SLIPPAGE,
                    simulate=False  # Set to True for testing
                )
            
            if result.get('success', False):
                # Update trade record with success
                await self.db_manager.update_trade_status(
                    trade.id,
                    TradeStatus.EXECUTED,
                    transaction_hash=result.get('transactionHash'),
                    output_amount=result.get('actualOutput', 0)
                )
                
                success_text = f"""
✅ **Investment Successful!**

**Transaction Details:**
• Amount: ${amount:.2f} USDC
• Output: {result.get('actualOutput', 0):.6f} {output_token}
• Transaction: `{result.get('transactionHash', 'N/A')}`
• Gas Used: {result.get('gasUsed', 'N/A')}

**Pool:** {pool_data.get('tokenA', '')}/{pool_data.get('tokenB', '')}
**Expected APY:** {pool_data.get('apy', 0):.2f}%

Your investment is now earning yield! Use /report to track your performance.
                """
                
                await query.edit_message_text(
                    text=success_text,
                    parse_mode='Markdown'
                )
                
            else:
                # Update trade record with failure
                error_msg = result.get('error', 'Unknown error')
                await self.db_manager.update_trade_status(
                    trade.id,
                    TradeStatus.FAILED,
                    error_message=error_msg
                )
                
                failure_text = f"""
❌ **Investment Failed**

**Error:** {error_msg}

Your funds have not been transferred. Please try again or contact support if the issue persists.
                """
                
                keyboard = [[
                    InlineKeyboardButton("🔄 Try Again", callback_data=f"pool_details:{pool_id}")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text=failure_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error executing investment: {e}")
            
            # Update trade record with error
            if 'trade' in locals():
                await self.db_manager.update_trade_status(
                    trade.id,
                    TradeStatus.FAILED,
                    error_message=str(e)
                )
            
            await query.edit_message_text(
                "❌ **Investment Failed**\n\nAn unexpected error occurred. Please try again later."
            )
    
    async def _handle_refresh_pools(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Handle pool refresh request."""
        try:
            async with FiLotClient(self.config) as client:
                pools_data = await client.get_pools()
            
            if not pools_data:
                await query.edit_message_text("❌ No pools available at the moment.")
                return
            
            # Filter and sort pools
            high_yield_pools = [
                pool for pool in pools_data 
                if pool.get('apy', 0) >= self.config.MIN_APR_THRESHOLD
                and pool.get('tvl', 0) >= self.config.MIN_TVL_THRESHOLD
            ]
            
            if not high_yield_pools:
                await query.edit_message_text(
                    f"❌ No pools meet the minimum criteria (APY > {self.config.MIN_APR_THRESHOLD}%, TVL > ${self.config.MIN_TVL_THRESHOLD:,.0f})"
                )
                return
            
            high_yield_pools.sort(key=lambda x: x.get('apy', 0), reverse=True)
            
            # Create keyboard
            keyboard = []
            for i, pool in enumerate(high_yield_pools[:10]):
                pool_text = f"🏊 {pool.get('tokenA', 'Unknown')}/{pool.get('tokenB', 'Unknown')} - {pool.get('apy', 0):.1f}% APY"
                keyboard.append([
                    InlineKeyboardButton(
                        pool_text,
                        callback_data=f"pool_details:{pool.get('poolId')}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("🔄 Refresh Pools", callback_data="refresh_pools")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = f"""
💰 **High-Yield Investment Opportunities** 🔄

Found {len(high_yield_pools)} pools meeting your criteria:
• Min APY: {self.config.MIN_APR_THRESHOLD}%
• Min TVL: ${self.config.MIN_TVL_THRESHOLD:,.0f}

Select a pool below to view details and invest:
            """
            
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error refreshing pools: {e}")
            await query.edit_message_text("❌ Unable to refresh pools. Please try again.")
    
    async def _handle_settings(self, query, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Handle settings callbacks."""
        setting_type = callback_data.replace("setting_", "")
        
        # This would implement settings modification UI
        # For now, show a placeholder
        await query.edit_message_text(
            f"⚙️ **{setting_type.replace('_', ' ').title()} Settings**\n\n"
            "Settings modification UI coming soon! Use /settings to view current settings.",
            parse_mode='Markdown'
        )
    
    async def _handle_customize_settings(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Handle customize settings callback."""
        keyboard = [
            [InlineKeyboardButton("📊 APY Threshold", callback_data="setting_apy_threshold")],
            [InlineKeyboardButton("⚠️ Risk Level", callback_data="setting_risk_level")],
            [InlineKeyboardButton("💰 Daily Limit", callback_data="setting_daily_limit")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ **Customize Your Settings**\n\nSelect a setting to modify:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
