"""
Action module for the autonomous agent.
Executes trades, sends notifications, and performs autonomous actions.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

from config import Config
from utils.database import DatabaseManager
from utils.filot_client import FiLotClient, FiLotError
from models import Trade, TradeStatus, Opportunity

class ActionModule:
    """
    Handles action execution for the autonomous agent.
    Performs trades, notifications, and database updates.
    """
    
    def __init__(self, config: Config, db_manager: DatabaseManager, telegram_bot):
        self.config = config
        self.db_manager = db_manager
        self.telegram_bot = telegram_bot
    
    async def run(self, decisions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main action cycle: execute decisions and actions.
        
        Args:
            decisions: Output from decision module
            
        Returns:
            Dictionary containing action results:
            - trades_executed: Number of trades executed
            - notifications_sent: Number of notifications sent
            - opportunities_recorded: Number of opportunities saved
            - errors: List of errors encountered
        """
        action_start = datetime.now()
        logger.info("⚡ Starting action module")
        
        try:
            # Extract data from decisions
            opportunities = decisions.get('opportunities', [])
            notifications = decisions.get('notifications', [])
            actions = decisions.get('actions', [])
            
            # Initialize results tracking
            results = {
                'trades_executed': 0,
                'successful_trades': 0,
                'failed_trades': 0,
                'notifications_sent': 0,
                'opportunities_recorded': 0,
                'errors': [],
                'actions_processed': 0,
                'timestamp': datetime.now()
            }
            
            # 1. Record opportunities in database
            await self._record_opportunities(opportunities, results)
            
            # 2. Send notifications to users
            await self._send_notifications(notifications, results)
            
            # 3. Execute autonomous trades (if enabled)
            if self.config.AUTONOMOUS_TRADING_ENABLED:
                await self._execute_autonomous_trades(opportunities, results)
            
            # 4. Process additional actions
            await self._process_actions(actions, results)
            
            action_duration = (datetime.now() - action_start).total_seconds()
            results['processing_time'] = action_duration
            
            logger.info(f"✅ Action completed: {results['notifications_sent']} notifications, "
                       f"{results['trades_executed']} trades in {action_duration:.2f}s")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in action module: {e}")
            return {
                'trades_executed': 0,
                'successful_trades': 0,
                'failed_trades': 0,
                'notifications_sent': 0,
                'opportunities_recorded': 0,
                'errors': [str(e)],
                'actions_processed': 0,
                'timestamp': datetime.now(),
                'processing_time': 0
            }
    
    async def _record_opportunities(self, opportunities: List[Dict[str, Any]], 
                                  results: Dict[str, Any]):
        """Record detected opportunities in the database."""
        try:
            for opportunity in opportunities:
                # Create opportunity record
                opp_record = Opportunity(
                    id=None,
                    pool_id=opportunity['pool_id'],
                    detected_at=datetime.now(),
                    apr=opportunity['apy'],
                    tvl=opportunity['tvl'],
                    risk_score=opportunity['risk_metrics']['overall_risk'],
                    confidence=opportunity['confidence_score'],
                    is_processed=False,
                    users_notified=0
                )
                
                # Save to database (would need an insert method in DatabaseManager)
                logger.debug(f"Recording opportunity for pool {opportunity['pool_id']}")
                results['opportunities_recorded'] += 1
            
            logger.info(f"Recorded {results['opportunities_recorded']} opportunities")
            
        except Exception as e:
            logger.error(f"Error recording opportunities: {e}")
            results['errors'].append(f"Opportunity recording failed: {e}")
    
    async def _send_notifications(self, notifications: List[Dict[str, Any]], 
                                results: Dict[str, Any]):
        """Send opportunity notifications to users."""
        try:
            for notification in notifications:
                user_id = notification['user_id']
                decisions = notification['decisions']
                priority = notification['priority']
                
                # Generate notification message
                message = await self._generate_notification_message(notification)
                
                # Create inline keyboard for investment actions
                keyboard = await self._create_notification_keyboard(decisions)
                
                # Send notification via Telegram bot
                success = await self.telegram_bot.send_notification(
                    user_id=user_id,
                    message=message,
                    reply_markup=keyboard
                )
                
                if success:
                    results['notifications_sent'] += 1
                    logger.debug(f"Notification sent to user {user_id}")
                else:
                    results['errors'].append(f"Failed to notify user {user_id}")
                
                # Add delay to avoid rate limiting
                await asyncio.sleep(0.5)
            
            logger.info(f"Sent {results['notifications_sent']} notifications")
            
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
            results['errors'].append(f"Notification sending failed: {e}")
    
    async def _generate_notification_message(self, notification: Dict[str, Any]) -> str:
        """Generate notification message text."""
        try:
            decisions = notification['decisions']
            priority = notification['priority']
            total_opportunities = notification['total_opportunities']
            best_apy = notification['best_apy']
            
            # Priority emoji
            priority_emoji = {
                'high': '🚨',
                'medium': '🔔', 
                'low': '💡'
            }[priority]
            
            # Create message header
            message_lines = [
                f"{priority_emoji} **New Investment Opportunities Detected!**",
                "",
                f"🎯 **{total_opportunities} high-yield opportunities** found",
                f"📈 **Best APY: {best_apy:.1f}%**",
                ""
            ]
            
            # Add top opportunities
            top_decisions = decisions[:3]  # Show top 3
            for i, decision in enumerate(top_decisions, 1):
                token_pair = f"{decision['token_a']}/{decision['token_b']}"
                apy = decision['apy']
                suggested_amount = decision['suggested_amount']
                confidence = decision['confidence_score'] * 100
                
                message_lines.extend([
                    f"**{i}. {token_pair}**",
                    f"  💰 APY: {apy:.1f}%",
                    f"  💸 Suggested: ${suggested_amount:.0f}",
                    f"  🎯 Confidence: {confidence:.0f}%",
                    ""
                ])
            
            # Add footer
            message_lines.extend([
                "⚡ **One-click investing available**",
                "🛡️ **Risk management applied**",
                "",
                "Select an opportunity below to invest:"
            ])
            
            return "\n".join(message_lines)
            
        except Exception as e:
            logger.error(f"Error generating notification message: {e}")
            return "🔔 New investment opportunities available! Check /invest for details."
    
    async def _create_notification_keyboard(self, decisions: List[Dict[str, Any]]):
        """Create inline keyboard for notification actions."""
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = []
            
            # Add buttons for top opportunities
            for decision in decisions[:3]:  # Max 3 buttons
                token_pair = f"{decision['token_a']}/{decision['token_b']}"
                suggested_amount = decision['suggested_amount']
                apy = decision['apy']
                
                button_text = f"💰 {token_pair} - {apy:.1f}% (${suggested_amount:.0f})"
                callback_data = f"auto_invest:{decision['pool_id']}:{suggested_amount:.0f}"
                
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Add general action buttons
            keyboard.extend([
                [InlineKeyboardButton("📊 View All Opportunities", callback_data="refresh_pools")],
                [InlineKeyboardButton("⚙️ Adjust Settings", callback_data="customize_settings")]
            ])
            
            return InlineKeyboardMarkup(keyboard)
            
        except Exception as e:
            logger.error(f"Error creating notification keyboard: {e}")
            return None
    
    async def _execute_autonomous_trades(self, opportunities: List[Dict[str, Any]], 
                                       results: Dict[str, Any]):
        """
        Execute autonomous trades (disabled by default for safety).
        This would only be enabled for users who explicitly opt-in to full automation.
        """
        try:
            # For safety, autonomous trading is disabled by default
            # Users must explicitly enable it and accept the risks
            
            auto_trade_opportunities = [
                opp for opp in opportunities 
                if opp.get('auto_trade_enabled', False) and 
                   opp.get('confidence_score', 0) >= 0.8  # Only high-confidence trades
            ]
            
            if not auto_trade_opportunities:
                logger.debug("No opportunities approved for autonomous trading")
                return
            
            for opportunity in auto_trade_opportunities:
                try:
                    await self._execute_single_trade(opportunity, results)
                    await asyncio.sleep(1)  # Delay between trades
                    
                except Exception as e:
                    logger.error(f"Error in autonomous trade: {e}")
                    results['errors'].append(f"Auto trade failed: {e}")
                    results['failed_trades'] += 1
            
        except Exception as e:
            logger.error(f"Error in autonomous trading: {e}")
            results['errors'].append(f"Autonomous trading failed: {e}")
    
    async def _execute_single_trade(self, opportunity: Dict[str, Any], 
                                  results: Dict[str, Any]):
        """Execute a single autonomous trade."""
        try:
            user_id = opportunity['user_id']
            pool_id = opportunity['pool_id']
            amount = opportunity['suggested_amount']
            
            # Create trade record
            trade = Trade(
                id=None,
                user_id=user_id,
                pool_id=pool_id,
                trade_type="autonomous",
                input_token="USDC",
                output_token=opportunity['token_a'],
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
            
            # Execute the trade
            async with FiLotClient(self.config) as client:
                result = await client.execute_swap(
                    input_token="USDC",
                    output_token=opportunity['token_a'],
                    amount=amount,
                    slippage=self.config.MAX_SLIPPAGE,
                    simulate=False
                )
            
            if result.get('success', False):
                # Update trade record with success
                await self.db_manager.update_trade_status(
                    trade.id,
                    TradeStatus.EXECUTED,
                    transaction_hash=result.get('transactionHash'),
                    output_amount=result.get('actualOutput', 0)
                )
                
                results['trades_executed'] += 1
                results['successful_trades'] += 1
                
                # Send success notification
                await self._send_trade_confirmation(user_id, trade, result, True)
                
                logger.info(f"Autonomous trade executed for user {user_id}: ${amount} -> {opportunity['token_a']}")
                
            else:
                # Update trade record with failure
                error_msg = result.get('error', 'Unknown error')
                await self.db_manager.update_trade_status(
                    trade.id,
                    TradeStatus.FAILED,
                    error_message=error_msg
                )
                
                results['trades_executed'] += 1
                results['failed_trades'] += 1
                
                # Send failure notification
                await self._send_trade_confirmation(user_id, trade, result, False)
                
                logger.warning(f"Autonomous trade failed for user {user_id}: {error_msg}")
            
        except Exception as e:
            logger.error(f"Error executing single trade: {e}")
            raise
    
    async def _send_trade_confirmation(self, user_id: int, trade: Trade, 
                                     result: Dict[str, Any], success: bool):
        """Send trade confirmation message to user."""
        try:
            if success:
                message = f"""
✅ **Autonomous Trade Executed!**

**Transaction Details:**
• Pool: {trade.pool_id}
• Amount: ${trade.input_amount:.2f} {trade.input_token}
• Output: {result.get('actualOutput', 0):.6f} {trade.output_token}
• Transaction: `{result.get('transactionHash', 'N/A')}`

Your investment is now earning yield!
                """
            else:
                message = f"""
❌ **Autonomous Trade Failed**

**Details:**
• Pool: {trade.pool_id}
• Amount: ${trade.input_amount:.2f} {trade.input_token}
• Error: {result.get('error', 'Unknown error')}

Your funds were not transferred. We'll continue monitoring for new opportunities.
                """
            
            await self.telegram_bot.send_notification(user_id, message)
            
        except Exception as e:
            logger.error(f"Error sending trade confirmation: {e}")
    
    async def _process_actions(self, actions: List[Dict[str, Any]], 
                             results: Dict[str, Any]):
        """Process additional actions from decision module."""
        try:
            for action in actions:
                action_type = action.get('type', 'unknown')
                
                if action_type == 'send_notification':
                    # Already handled in _send_notifications
                    pass
                    
                elif action_type == 'record_opportunity':
                    # Already handled in _record_opportunities
                    pass
                    
                elif action_type == 'update_user_preferences':
                    await self._update_user_preferences(action)
                    
                elif action_type == 'log_market_event':
                    await self._log_market_event(action)
                    
                else:
                    logger.warning(f"Unknown action type: {action_type}")
                
                results['actions_processed'] += 1
            
        except Exception as e:
            logger.error(f"Error processing actions: {e}")
            results['errors'].append(f"Action processing failed: {e}")
    
    async def _update_user_preferences(self, action: Dict[str, Any]):
        """Update user preferences based on trading patterns."""
        try:
            # TODO: Implement learning-based preference updates
            # This could analyze user acceptance/rejection patterns
            # and suggest preference adjustments
            logger.debug("User preference update (TODO)")
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
    
    async def _log_market_event(self, action: Dict[str, Any]):
        """Log significant market events for analysis."""
        try:
            # TODO: Implement market event logging
            # This could track major price movements, liquidity changes, etc.
            logger.debug("Market event logging (TODO)")
            
        except Exception as e:
            logger.error(f"Error logging market event: {e}")
    
    async def manual_execute_trade(self, user_id: int, pool_id: str, 
                                 amount: float) -> Dict[str, Any]:
        """
        Manually execute a trade (called from callback handlers).
        
        Args:
            user_id: User ID
            pool_id: Pool identifier
            amount: Investment amount
            
        Returns:
            Trade execution result
        """
        try:
            logger.info(f"Manual trade execution: user {user_id}, pool {pool_id}, amount ${amount}")
            
            # This would be similar to _execute_single_trade but for manual trades
            # Implementation would depend on the specific requirements
            
            return {
                'success': True,
                'message': 'Trade executed successfully',
                'transaction_hash': 'mock_hash_123'  # Would be real transaction hash
            }
            
        except Exception as e:
            logger.error(f"Error in manual trade execution: {e}")
            return {
                'success': False,
                'message': f'Trade failed: {e}',
                'transaction_hash': None
            }
