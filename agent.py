"""
Autonomous agent for the Telegram trading bot.
Implements the agentic layer with perception, decision, action, and learning modules.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import Config
from utils.database import DatabaseManager
from utils.filot_client import FiLotClient
from modules.perception import PerceptionModule
from modules.decision import DecisionModule
from modules.action import ActionModule
from modules.notification import NotificationModule
from models import AgentState

class AutonomousAgent:
    """
    Main autonomous agent that coordinates all agentic modules.
    Implements the perception → decision → action → learning cycle.
    """
    
    def __init__(self, config: Config, db_manager: DatabaseManager, telegram_bot):
        self.config = config
        self.db_manager = db_manager
        self.telegram_bot = telegram_bot
        
        # Initialize modules
        self.perception = PerceptionModule(config, db_manager)
        self.decision = DecisionModule(config, db_manager)
        self.action = ActionModule(config, db_manager, telegram_bot)
        self.notification = NotificationModule(config, db_manager, telegram_bot)
        
        # Scheduler for autonomous operations
        self.scheduler = AsyncIOScheduler()
        
        # Agent state tracking
        self.agent_state = AgentState(
            id=1,
            last_perception_run=datetime.min,
            last_decision_run=datetime.min,
            last_action_run=datetime.min,
            pools_monitored=0,
            opportunities_detected=0,
            trades_executed=0,
            errors_count=0,
            updated_at=datetime.now()
        )
        
        self.is_running = False
        logger.info("Autonomous agent initialized")
    
    async def start(self):
        """Start the autonomous agent with scheduled tasks."""
        try:
            # Load existing state from database
            existing_state = await self.db_manager.get_agent_state()
            if existing_state:
                self.agent_state = existing_state
            
            # Schedule the main perception-decision-action cycle
            self.scheduler.add_job(
                self._run_cycle,
                trigger=IntervalTrigger(seconds=self.config.MONITORING_INTERVAL),
                id='main_cycle',
                max_instances=1,
                coalesce=True
            )
            
            # Schedule health checks every hour
            self.scheduler.add_job(
                self._health_check,
                trigger=IntervalTrigger(hours=1),
                id='health_check',
                max_instances=1
            )
            
            # Schedule daily reports
            self.scheduler.add_job(
                self._daily_report,
                trigger=IntervalTrigger(hours=24),
                id='daily_report',
                max_instances=1
            )
            
            # Start scheduler
            self.scheduler.start()
            self.is_running = True
            
            logger.info(f"Autonomous agent started with {self.config.MONITORING_INTERVAL}s monitoring interval")
            
            # Run initial cycle
            await self._run_cycle()
            
        except Exception as e:
            logger.error(f"Failed to start autonomous agent: {e}")
            raise
    
    async def stop(self):
        """Stop the autonomous agent and cleanup."""
        try:
            self.is_running = False
            
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            
            # Save final state
            await self._update_agent_state()
            
            logger.info("Autonomous agent stopped")
            
        except Exception as e:
            logger.error(f"Error stopping autonomous agent: {e}")
    
    async def _run_cycle(self):
        """
        Main agent cycle: Perception → Decision → Action → Learning
        """
        if not self.is_running:
            return
        
        cycle_start = datetime.now()
        logger.info("Starting agent cycle")
        
        try:
            # 1. PERCEPTION: Gather market data and analyze pools
            logger.info("🔍 Running perception module...")
            perception_data = await self.perception.run()
            
            self.agent_state.last_perception_run = datetime.now()
            self.agent_state.pools_monitored = len(perception_data.get('pools', []))
            
            # 2. DECISION: Analyze opportunities and make trading decisions
            logger.info("🧠 Running decision module...")
            decisions = await self.decision.run(perception_data)
            
            self.agent_state.last_decision_run = datetime.now()
            self.agent_state.opportunities_detected += len(decisions.get('opportunities', []))
            
            # 3. ACTION: Execute trades and send notifications
            logger.info("⚡ Running action module...")
            action_results = await self.action.run(decisions)
            
            self.agent_state.last_action_run = datetime.now()
            self.agent_state.trades_executed += action_results.get('trades_executed', 0)
            
            # 4. LEARNING: Analyze results and adjust strategies (stub for now)
            await self._learning_cycle(perception_data, decisions, action_results)
            
            # Update agent state
            await self._update_agent_state()
            
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(f"✅ Agent cycle completed in {cycle_duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Error in agent cycle: {e}")
            self.agent_state.errors_count += 1
            await self._update_agent_state()
    
    async def _learning_cycle(self, perception_data: Dict, decisions: Dict, action_results: Dict):
        """
        Learning module (stub implementation).
        Future: Integrate with RL/LLM for strategy optimization.
        """
        try:
            # TODO: Implement learning capabilities
            # - Analyze trade outcomes vs predictions
            # - Adjust decision thresholds based on performance
            # - Update risk models based on realized outcomes
            # - Train ML models if OpenAI integration is available
            
            if self.config.is_openai_enabled:
                # TODO: Implement OpenAI integration for strategy analysis
                logger.debug("OpenAI learning integration (TODO)")
            
            # For now, simple rule-based adjustments
            opportunities = decisions.get('opportunities', [])
            successful_trades = action_results.get('successful_trades', 0)
            failed_trades = action_results.get('failed_trades', 0)
            
            if opportunities and (successful_trades + failed_trades) > 0:
                success_rate = successful_trades / (successful_trades + failed_trades)
                logger.info(f"📚 Learning: Success rate: {success_rate:.2%}, Opportunities: {len(opportunities)}")
                
                # Simple threshold adjustment based on success rate
                if success_rate < 0.5:
                    logger.info("💡 Learning: Low success rate, tightening decision criteria")
                elif success_rate > 0.8:
                    logger.info("💡 Learning: High success rate, loosening decision criteria")
            
        except Exception as e:
            logger.error(f"Error in learning cycle: {e}")
    
    async def _health_check(self):
        """Perform health checks on agent components."""
        try:
            logger.info("🏥 Running health check...")
            
            # Check FiLot API connectivity
            async with FiLotClient(self.config) as client:
                api_healthy = await client.health_check()
            
            # Check database connectivity
            agent_state = await self.db_manager.get_agent_state()
            db_healthy = agent_state is not None
            
            # Check recent activity
            time_since_last_run = datetime.now() - self.agent_state.last_perception_run
            agent_active = time_since_last_run.total_seconds() < self.config.MONITORING_INTERVAL * 2
            
            health_status = {
                'api_healthy': api_healthy,
                'db_healthy': db_healthy,
                'agent_active': agent_active,
                'timestamp': datetime.now()
            }
            
            if not all(health_status.values()):
                logger.warning(f"Health check issues detected: {health_status}")
                # TODO: Send alert to admin
            else:
                logger.info("✅ Health check passed")
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.agent_state.errors_count += 1
    
    async def _daily_report(self):
        """Generate and send daily performance reports."""
        try:
            logger.info("📊 Generating daily report...")
            
            # Generate report data
            report_data = {
                'date': datetime.now().date(),
                'pools_monitored': self.agent_state.pools_monitored,
                'opportunities_detected': self.agent_state.opportunities_detected,
                'trades_executed': self.agent_state.trades_executed,
                'errors_count': self.agent_state.errors_count
            }
            
            # Send reports to subscribed users
            await self.notification.send_daily_reports(report_data)
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
    
    async def _update_agent_state(self):
        """Update agent state in the database."""
        try:
            self.agent_state.updated_at = datetime.now()
            await self.db_manager.update_agent_state(self.agent_state)
        except Exception as e:
            logger.error(f"Failed to update agent state: {e}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            'is_running': self.is_running,
            'last_perception_run': self.agent_state.last_perception_run,
            'last_decision_run': self.agent_state.last_decision_run,
            'last_action_run': self.agent_state.last_action_run,
            'pools_monitored': self.agent_state.pools_monitored,
            'opportunities_detected': self.agent_state.opportunities_detected,
            'trades_executed': self.agent_state.trades_executed,
            'errors_count': self.agent_state.errors_count,
            'next_run': self.scheduler.get_job('main_cycle').next_run_time if self.scheduler.running else None
        }
    
    async def manual_trigger(self) -> Dict[str, Any]:
        """Manually trigger an agent cycle (for testing/debugging)."""
        logger.info("Manual agent cycle triggered")
        await self._run_cycle()
        return await self.get_status()
