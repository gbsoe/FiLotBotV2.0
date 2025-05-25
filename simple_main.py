"""
Simple test version of the Precision Investing Telegram Bot.
This version checks basic functionality and API connectivity.
"""

import asyncio
import os
from loguru import logger
from config import Config
from utils.database import DatabaseManager
from utils.filot_client import FiLotClient

async def test_bot_components():
    """
    Test the core bot components without Telegram integration.
    """
    logger.add("logs/test_{time}.log", rotation="1 day")
    logger.info("Testing Precision Investing Bot components...")
    
    try:
        # Load configuration
        config = Config()
        logger.info("✅ Configuration loaded successfully")
        
        # Test database initialization
        db_manager = DatabaseManager(config.DATABASE_PATH)
        await db_manager.initialize()
        logger.info("✅ Database initialized successfully")
        
        # Test FiLot API connectivity (this will need real API keys)
        try:
            async with FiLotClient(config) as client:
                # Test API health check
                is_healthy = await client.health_check()
                if is_healthy:
                    logger.info("✅ FiLot API connection successful")
                    
                    # Try to fetch pools
                    pools = await client.get_pools()
                    logger.info(f"✅ Fetched {len(pools)} pools from FiLot API")
                else:
                    logger.warning("⚠️ FiLot API health check failed")
                    
        except Exception as e:
            logger.warning(f"⚠️ FiLot API connection failed: {e}")
            logger.info("This is expected if API keys are not configured yet")
        
        # Test agent state management
        from models import AgentState
        from datetime import datetime
        
        test_state = AgentState(
            id=1,
            last_perception_run=datetime.now(),
            last_decision_run=datetime.now(),
            last_action_run=datetime.now(),
            pools_monitored=0,
            opportunities_detected=0,
            trades_executed=0,
            errors_count=0,
            updated_at=datetime.now()
        )
        
        await db_manager.update_agent_state(test_state)
        logger.info("✅ Agent state management working")
        
        # Cleanup
        await db_manager.close()
        
        logger.info("🎉 Core components test completed successfully!")
        logger.info("Ready for Telegram bot integration with proper API keys")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Component test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_bot_components())
    if success:
        print("\n🎉 Bot components are working correctly!")
        print("Next steps:")
        print("1. Add your TELEGRAM_TOKEN to .env")
        print("2. Add your FILOT_BASE_URL and SOLANA_PRIVATE_KEY to .env")
        print("3. Run the full bot with proper Telegram integration")
    else:
        print("\n❌ Some components need attention before proceeding")