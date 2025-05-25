"""
Database manager for SQLite operations using aiosqlite.
Handles all database interactions for the bot.
"""

import aiosqlite
from datetime import datetime
from typing import List, Optional, Dict, Any
from loguru import logger
from models import (
    User, Subscription, Pool, Trade, AgentState, Opportunity,
    SubscriptionStatus, TradeStatus, SCHEMA_SQL
)

class DatabaseManager:
    """Manages all database operations for the bot."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection = None
    
    async def initialize(self):
        """Initialize the database and create tables."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript(SCHEMA_SQL)
                await db.commit()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
    
    # User operations
    async def create_or_update_user(self, user_data: Dict[str, Any]) -> User:
        """Create or update a user in the database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_data['user_id'],
                user_data.get('username'),
                user_data.get('first_name'),
                user_data.get('last_name'),
                datetime.now()
            ))
            await db.commit()
            
            # Fetch the user
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", 
                (user_data['user_id'],)
            )
            row = await cursor.fetchone()
            
            if row:
                return User(
                    user_id=row[0],
                    username=row[1],
                    first_name=row[2],
                    last_name=row[3],
                    created_at=datetime.fromisoformat(row[4]),
                    updated_at=datetime.fromisoformat(row[5]),
                    is_active=bool(row[6])
                )
            
            raise ValueError("Failed to create/update user")
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """Get a user by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return User(
                    user_id=row[0],
                    username=row[1],
                    first_name=row[2],
                    last_name=row[3],
                    created_at=datetime.fromisoformat(row[4]),
                    updated_at=datetime.fromisoformat(row[5]),
                    is_active=bool(row[6])
                )
            return None
    
    # Subscription operations
    async def create_subscription(self, subscription: Subscription) -> Subscription:
        """Create a new subscription."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO subscriptions 
                (user_id, status, min_apr_threshold, max_risk_level, max_daily_investment)
                VALUES (?, ?, ?, ?, ?)
            """, (
                subscription.user_id,
                subscription.status.value,
                subscription.min_apr_threshold,
                subscription.max_risk_level,
                subscription.max_daily_investment
            ))
            await db.commit()
            
            subscription.id = cursor.lastrowid
            return subscription
    
    async def get_subscription(self, user_id: int) -> Optional[Subscription]:
        """Get user's subscription."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return Subscription(
                    id=row[0],
                    user_id=row[1],
                    status=SubscriptionStatus(row[2]),
                    min_apr_threshold=row[3],
                    max_risk_level=row[4],
                    max_daily_investment=row[5],
                    created_at=datetime.fromisoformat(row[6]),
                    updated_at=datetime.fromisoformat(row[7])
                )
            return None
    
    async def get_active_subscriptions(self) -> List[Subscription]:
        """Get all active subscriptions."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM subscriptions WHERE status = 'active'"
            )
            rows = await cursor.fetchall()
            
            return [
                Subscription(
                    id=row[0],
                    user_id=row[1],
                    status=SubscriptionStatus(row[2]),
                    min_apr_threshold=row[3],
                    max_risk_level=row[4],
                    max_daily_investment=row[5],
                    created_at=datetime.fromisoformat(row[6]),
                    updated_at=datetime.fromisoformat(row[7])
                )
                for row in rows
            ]
    
    # Pool operations
    async def update_pool(self, pool: Pool):
        """Update pool data."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO pools 
                (pool_id, token_a, token_b, tvl, volume_24h, apy, fee_rate, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pool.pool_id,
                pool.token_a,
                pool.token_b,
                pool.tvl,
                pool.volume_24h,
                pool.apy,
                pool.fee_rate,
                pool.last_updated
            ))
            await db.commit()
    
    async def get_pools(self) -> List[Pool]:
        """Get all pools."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM pools ORDER BY apy DESC")
            rows = await cursor.fetchall()
            
            return [
                Pool(
                    pool_id=row[0],
                    token_a=row[1],
                    token_b=row[2],
                    tvl=row[3],
                    volume_24h=row[4],
                    apy=row[5],
                    fee_rate=row[6],
                    last_updated=datetime.fromisoformat(row[7])
                )
                for row in rows
            ]
    
    # Trade operations
    async def create_trade(self, trade: Trade) -> Trade:
        """Create a new trade record."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO trades 
                (user_id, pool_id, trade_type, input_token, output_token, 
                 input_amount, output_amount, slippage, transaction_hash, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.user_id,
                trade.pool_id,
                trade.trade_type,
                trade.input_token,
                trade.output_token,
                trade.input_amount,
                trade.output_amount,
                trade.slippage,
                trade.transaction_hash,
                trade.status.value
            ))
            await db.commit()
            
            trade.id = cursor.lastrowid
            return trade
    
    async def update_trade_status(self, trade_id: int, status: TradeStatus, 
                                 transaction_hash: Optional[str] = None,
                                 output_amount: Optional[float] = None,
                                 error_message: Optional[str] = None):
        """Update trade status and details."""
        async with aiosqlite.connect(self.db_path) as db:
            executed_at = datetime.now() if status == TradeStatus.EXECUTED else None
            
            await db.execute("""
                UPDATE trades 
                SET status = ?, transaction_hash = ?, output_amount = ?, 
                    executed_at = ?, error_message = ?
                WHERE id = ?
            """, (
                status.value,
                transaction_hash,
                output_amount,
                executed_at,
                error_message,
                trade_id
            ))
            await db.commit()
    
    async def get_user_daily_exposure(self, user_id: int) -> float:
        """Get user's total exposure for the current day."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT SUM(input_amount) FROM trades 
                WHERE user_id = ? AND DATE(created_at) = DATE('now')
                AND status IN ('executed', 'pending')
            """, (user_id,))
            result = await cursor.fetchone()
            return result[0] if result[0] else 0.0
    
    # Agent state operations
    async def update_agent_state(self, state: AgentState):
        """Update agent state."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO agent_state 
                (id, last_perception_run, last_decision_run, last_action_run,
                 pools_monitored, opportunities_detected, trades_executed, 
                 errors_count, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                state.last_perception_run,
                state.last_decision_run,
                state.last_action_run,
                state.pools_monitored,
                state.opportunities_detected,
                state.trades_executed,
                state.errors_count,
                state.updated_at
            ))
            await db.commit()
    
    async def get_agent_state(self) -> Optional[AgentState]:
        """Get current agent state."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM agent_state WHERE id = 1")
            row = await cursor.fetchone()
            
            if row:
                return AgentState(
                    id=row[0],
                    last_perception_run=datetime.fromisoformat(row[1]) if row[1] else datetime.min,
                    last_decision_run=datetime.fromisoformat(row[2]) if row[2] else datetime.min,
                    last_action_run=datetime.fromisoformat(row[3]) if row[3] else datetime.min,
                    pools_monitored=row[4],
                    opportunities_detected=row[5],
                    trades_executed=row[6],
                    errors_count=row[7],
                    updated_at=datetime.fromisoformat(row[8])
                )
            return None
