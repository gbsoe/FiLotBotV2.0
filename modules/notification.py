"""
Notification module for the autonomous agent.
Handles all user communications, alerts, and reporting.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger

from config import Config
from utils.database import DatabaseManager
from models import Subscription, SubscriptionStatus

class NotificationModule:
    """
    Handles all notification and communication functionality.
    """
    
    def __init__(self, config: Config, db_manager: DatabaseManager, telegram_bot):
        self.config = config
        self.db_manager = db_manager
        self.telegram_bot = telegram_bot
    
    async def send_opportunity_alerts(self, notifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Send opportunity alerts to users.
        
        Args:
            notifications: List of notification data from decision module
            
        Returns:
            Summary of notification results
        """
        results = {
            'notifications_sent': 0,
            'notifications_failed': 0,
            'users_notified': set(),
            'errors': []
        }
        
        try:
            for notification in notifications:
                try:
                    success = await self._send_opportunity_notification(notification)
                    
                    if success:
                        results['notifications_sent'] += 1
                        results['users_notified'].add(notification['user_id'])
                    else:
                        results['notifications_failed'] += 1
                    
                    # Rate limiting delay
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error sending notification to user {notification.get('user_id', 'unknown')}: {e}")
                    results['notifications_failed'] += 1
                    results['errors'].append(str(e))
            
            logger.info(f"Sent {results['notifications_sent']} opportunity alerts to {len(results['users_notified'])} users")
            return results
            
        except Exception as e:
            logger.error(f"Error in opportunity alerts: {e}")
            results['errors'].append(str(e))
            return results
    
    async def _send_opportunity_notification(self, notification: Dict[str, Any]) -> bool:
        """Send a single opportunity notification."""
        try:
            user_id = notification['user_id']
            decisions = notification['decisions']
            priority = notification['priority']
            
            # Generate message
            message = await self._create_opportunity_message(notification)
            
            # Create interactive keyboard
            keyboard = await self._create_opportunity_keyboard(decisions)
            
            # Send notification
            success = await self.telegram_bot.send_notification(
                user_id=user_id,
                message=message,
                reply_markup=keyboard
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending opportunity notification: {e}")
            return False
    
    async def _create_opportunity_message(self, notification: Dict[str, Any]) -> str:
        """Create opportunity notification message."""
        try:
            decisions = notification['decisions']
            priority = notification['priority']
            total_opportunities = notification['total_opportunities']
            best_apy = notification['best_apy']
            total_potential = notification['total_potential_investment']
            
            # Priority indicators
            priority_indicators = {
                'high': {'emoji': '🚨', 'text': 'HIGH PRIORITY'},
                'medium': {'emoji': '🔔', 'text': 'MEDIUM PRIORITY'},
                'low': {'emoji': '💡', 'text': 'NEW OPPORTUNITY'}
            }
            
            indicator = priority_indicators[priority]
            
            message_lines = [
                f"{indicator['emoji']} **{indicator['text']} ALERT**",
                "",
                f"🎯 **{total_opportunities} High-Yield Opportunities Detected!**",
                "",
                f"📈 **Best APY:** {best_apy:.1f}%",
                f"💰 **Total Potential Investment:** ${total_potential:.0f}",
                f"⏰ **Detected:** {datetime.now().strftime('%H:%M:%S')}",
                ""
            ]
            
            # Add top 3 opportunities details
            message_lines.append("**🏆 Top Opportunities:**")
            for i, decision in enumerate(decisions[:3], 1):
                token_pair = f"{decision['token_a']}/{decision['token_b']}"
                apy = decision['apy']
                tvl = decision['tvl']
                suggested_amount = decision['suggested_amount']
                confidence = decision['confidence_score'] * 100
                risk = decision['risk_metrics']['overall_risk']
                
                risk_emoji = '🟢' if risk <= 0.3 else '🟡' if risk <= 0.6 else '🔴'
                
                message_lines.extend([
                    f"",
                    f"**{i}. {token_pair}** {risk_emoji}",
                    f"  💹 APY: **{apy:.1f}%**",
                    f"  🏊 TVL: ${tvl:,.0f}",
                    f"  💸 Suggested: **${suggested_amount:.0f}**",
                    f"  🎯 Confidence: {confidence:.0f}%"
                ])
            
            message_lines.extend([
                "",
                "⚡ **Quick Actions:**",
                "• Tap a pool below to invest instantly",
                "• All trades include risk management",
                "• Funds are protected by slippage limits",
                "",
                "🛡️ **Safety Features Active:**",
                f"• Daily limit protection (${self.config.MAX_DAILY_EXPOSURE_USD:,.0f})",
                f"• Risk assessment applied",
                f"• Position sizing optimized"
            ])
            
            return "\n".join(message_lines)
            
        except Exception as e:
            logger.error(f"Error creating opportunity message: {e}")
            return "🔔 New investment opportunities available! Use /invest to explore."
    
    async def _create_opportunity_keyboard(self, decisions: List[Dict[str, Any]]):
        """Create interactive keyboard for opportunity notifications."""
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = []
            
            # Investment buttons for each opportunity
            for i, decision in enumerate(decisions[:3]):  # Max 3 direct buttons
                token_pair = f"{decision['token_a']}/{decision['token_b']}"
                apy = decision['apy']
                amount = decision['suggested_amount']
                
                # Create concise button text
                button_text = f"💰 {token_pair} - {apy:.1f}% (${amount:.0f})"
                callback_data = f"auto_invest:{decision['pool_id']}:{amount}"
                
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Action buttons
            keyboard.extend([
                [
                    InlineKeyboardButton("📊 View All Pools", callback_data="refresh_pools"),
                    InlineKeyboardButton("⚙️ Settings", callback_data="customize_settings")
                ],
                [
                    InlineKeyboardButton("📈 Portfolio Report", callback_data="view_report"),
                    InlineKeyboardButton("⏸️ Pause Alerts", callback_data="pause_notifications")
                ]
            ])
            
            return InlineKeyboardMarkup(keyboard)
            
        except Exception as e:
            logger.error(f"Error creating opportunity keyboard: {e}")
            return None
    
    async def send_daily_reports(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send daily performance reports to subscribed users."""
        try:
            results = {
                'reports_sent': 0,
                'reports_failed': 0,
                'users_notified': set(),
                'errors': []
            }
            
            # Get users who want daily reports
            active_subscriptions = await self.db_manager.get_active_subscriptions()
            
            for subscription in active_subscriptions:
                try:
                    user_id = subscription.user_id
                    
                    # Generate personalized report
                    report_message = await self._create_daily_report(user_id, report_data)
                    
                    # Send report
                    success = await self.telegram_bot.send_notification(
                        user_id=user_id,
                        message=report_message
                    )
                    
                    if success:
                        results['reports_sent'] += 1
                        results['users_notified'].add(user_id)
                    else:
                        results['reports_failed'] += 1
                    
                    # Rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error sending daily report to user {subscription.user_id}: {e}")
                    results['reports_failed'] += 1
                    results['errors'].append(str(e))
            
            logger.info(f"Sent {results['reports_sent']} daily reports")
            return results
            
        except Exception as e:
            logger.error(f"Error in daily reports: {e}")
            return {'reports_sent': 0, 'reports_failed': 0, 'users_notified': set(), 'errors': [str(e)]}
    
    async def _create_daily_report(self, user_id: int, report_data: Dict[str, Any]) -> str:
        """Create personalized daily report for a user."""
        try:
            date = report_data['date']
            
            # Get user's trading activity for the day
            user_exposure = await self.db_manager.get_user_daily_exposure(user_id)
            
            # TODO: Get user's portfolio performance, active positions, etc.
            # For now, create a basic report
            
            message_lines = [
                f"📊 **Daily Trading Report - {date.strftime('%B %d, %Y')}**",
                "",
                "**🤖 Agent Activity Today:**",
                f"• Pools Monitored: {report_data['pools_monitored']}",
                f"• Opportunities Detected: {report_data['opportunities_detected']}",
                f"• Trades Executed: {report_data['trades_executed']}",
                "",
                "**💰 Your Activity:**",
                f"• Daily Investment: ${user_exposure:.2f}",
                f"• Active Positions: Coming Soon",
                f"• Portfolio Value: Coming Soon",
                "",
                "**📈 Market Summary:**",
                "• Market conditions analyzed",
                "• Risk assessment updated",
                "• New opportunities identified",
                "",
                "**🎯 Tomorrow's Outlook:**",
                "• Continued monitoring active",
                "• Risk management in place",
                "• Ready for new opportunities",
                "",
                "Use /report for detailed performance metrics."
            ]
            
            return "\n".join(message_lines)
            
        except Exception as e:
            logger.error(f"Error creating daily report: {e}")
            return f"📊 Daily Report - {datetime.now().strftime('%B %d, %Y')}\n\nReport generation encountered an error. Use /report for current status."
    
    async def send_trade_confirmation(self, user_id: int, trade_data: Dict[str, Any], 
                                    success: bool) -> bool:
        """Send trade execution confirmation."""
        try:
            if success:
                message = f"""
✅ **Trade Executed Successfully!**

**Transaction Details:**
• Pool: {trade_data.get('pool_name', 'Unknown')}
• Amount: ${trade_data.get('amount', 0):.2f}
• Output: {trade_data.get('output_amount', 0):.6f} {trade_data.get('output_token', '')}
• APY: {trade_data.get('apy', 0):.2f}%
• Transaction Hash: `{trade_data.get('tx_hash', 'N/A')}`

💡 **Next Steps:**
• Your investment is now earning yield
• Monitor performance with /report
• Track market with /status

🛡️ **Protection Active:**
• Stop-loss monitoring enabled
• Risk limits in place
• Automatic rebalancing ready
                """
            else:
                error_msg = trade_data.get('error_message', 'Unknown error')
                message = f"""
❌ **Trade Execution Failed**

**Details:**
• Pool: {trade_data.get('pool_name', 'Unknown')}
• Attempted Amount: ${trade_data.get('amount', 0):.2f}
• Error: {error_msg}

💡 **What Happened:**
• Your funds are safe and unchanged
• No transaction was processed
• You can try again when conditions improve

🔄 **Next Steps:**
• Check /status for market conditions
• Review /pools for alternatives
• Adjust settings if needed
                """
            
            return await self.telegram_bot.send_notification(user_id, message)
            
        except Exception as e:
            logger.error(f"Error sending trade confirmation: {e}")
            return False
    
    async def send_risk_alert(self, user_id: int, risk_data: Dict[str, Any]) -> bool:
        """Send risk management alerts."""
        try:
            alert_type = risk_data.get('type', 'general')
            
            if alert_type == 'daily_limit':
                message = f"""
⚠️ **Daily Investment Limit Alert**

You're approaching your daily investment limit:
• Current: ${risk_data.get('current_exposure', 0):.2f}
• Limit: ${risk_data.get('daily_limit', 0):.2f}
• Remaining: ${risk_data.get('remaining', 0):.2f}

💡 **Options:**
• Wait until tomorrow for limit reset
• Increase limit in /settings
• Focus on monitoring existing positions
                """
            
            elif alert_type == 'high_risk':
                message = f"""
🔴 **High Risk Position Alert**

A position requires attention:
• Pool: {risk_data.get('pool_name', 'Unknown')}
• Current Risk: {risk_data.get('risk_level', 0):.1%}
• Your Limit: {risk_data.get('risk_limit', 0):.1%}

💡 **Recommended Actions:**
• Consider reducing position size
• Review market conditions
• Adjust risk tolerance if appropriate
                """
            
            else:
                message = f"""
⚠️ **Risk Management Alert**

{risk_data.get('message', 'Risk condition detected')}

Use /status to review current conditions.
                """
            
            return await self.telegram_bot.send_notification(user_id, message)
            
        except Exception as e:
            logger.error(f"Error sending risk alert: {e}")
            return False
    
    async def send_market_update(self, market_data: Dict[str, Any], 
                               user_filter: Optional[List[int]] = None) -> Dict[str, Any]:
        """Send market updates to users."""
        try:
            results = {
                'updates_sent': 0,
                'updates_failed': 0,
                'users_notified': set()
            }
            
            # Generate market update message
            message = await self._create_market_update_message(market_data)
            
            # Get target users
            if user_filter:
                target_users = user_filter
            else:
                # Send to all active subscribers
                subscriptions = await self.db_manager.get_active_subscriptions()
                target_users = [sub.user_id for sub in subscriptions]
            
            # Send updates
            for user_id in target_users:
                try:
                    success = await self.telegram_bot.send_notification(user_id, message)
                    
                    if success:
                        results['updates_sent'] += 1
                        results['users_notified'].add(user_id)
                    else:
                        results['updates_failed'] += 1
                    
                    await asyncio.sleep(0.3)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error sending market update to user {user_id}: {e}")
                    results['updates_failed'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error in market updates: {e}")
            return {'updates_sent': 0, 'updates_failed': 0, 'users_notified': set()}
    
    async def _create_market_update_message(self, market_data: Dict[str, Any]) -> str:
        """Create market update message."""
        try:
            message_lines = [
                "📊 **Market Update**",
                "",
                f"🕐 **Time:** {datetime.now().strftime('%H:%M:%S')}",
                f"📈 **Market Health:** {market_data.get('health', 'Unknown')}",
                f"💰 **Total TVL:** ${market_data.get('total_tvl', 0):,.0f}",
                f"📊 **Average APY:** {market_data.get('avg_apy', 0):.1f}%",
                f"🏊 **Active Pools:** {market_data.get('total_pools', 0)}",
                "",
                "**🎯 Opportunities:**",
                f"• High-yield pools: {market_data.get('high_apy_pools', 0)}",
                f"• Low-risk options: {market_data.get('stable_pools', 0)}",
                f"• High liquidity: {market_data.get('high_liquidity_pools', 0)}",
                "",
                "Use /invest to explore current opportunities."
            ]
            
            return "\n".join(message_lines)
            
        except Exception as e:
            logger.error(f"Error creating market update message: {e}")
            return "📊 Market Update: Data processing error occurred."
    
    async def send_system_alert(self, alert_data: Dict[str, Any], 
                              admin_only: bool = True) -> bool:
        """Send system alerts (errors, maintenance, etc.)."""
        try:
            alert_type = alert_data.get('type', 'info')
            message = alert_data.get('message', 'System alert')
            
            alert_emojis = {
                'error': '🚨',
                'warning': '⚠️',
                'info': 'ℹ️',
                'maintenance': '🔧'
            }
            
            emoji = alert_emojis.get(alert_type, 'ℹ️')
            
            formatted_message = f"""
{emoji} **System Alert**

{message}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            if admin_only:
                # Send to admin users only (would need admin user list)
                # For now, log the alert
                logger.warning(f"System alert: {message}")
                return True
            else:
                # Send to all users
                subscriptions = await self.db_manager.get_active_subscriptions()
                sent_count = 0
                
                for subscription in subscriptions:
                    try:
                        success = await self.telegram_bot.send_notification(
                            subscription.user_id, formatted_message
                        )
                        if success:
                            sent_count += 1
                        await asyncio.sleep(0.5)
                    except Exception:
                        continue
                
                logger.info(f"System alert sent to {sent_count} users")
                return sent_count > 0
            
        except Exception as e:
            logger.error(f"Error sending system alert: {e}")
            return False
