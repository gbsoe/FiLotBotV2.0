"""
Database models and schema definitions for the Telegram bot.
Uses SQLite with aiosqlite for asynchronous operations.
"""

from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum

class SubscriptionStatus(Enum):
    """User subscription status for autonomous trading."""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"

class TradeStatus(Enum):
    """Trade execution status."""
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class User:
    """User model for tracking bot users."""
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

@dataclass
class Subscription:
    """User subscription model for autonomous trading."""
    id: Optional[int]
    user_id: int
    status: SubscriptionStatus
    min_apr_threshold: float
    max_risk_level: float
    max_daily_investment: float
    created_at: datetime
    updated_at: datetime

@dataclass
class Pool:
    """Pool model for tracking Raydium pools."""
    pool_id: str
    token_a: str
    token_b: str
    tvl: float
    volume_24h: float
    apy: float
    fee_rate: float
    last_updated: datetime

@dataclass
class Trade:
    """Trade model for tracking all trading activity."""
    id: Optional[int]
    user_id: int
    pool_id: str
    trade_type: str  # 'manual' or 'autonomous'
    input_token: str
    output_token: str
    input_amount: float
    output_amount: Optional[float]
    slippage: float
    transaction_hash: Optional[str]
    status: TradeStatus
    created_at: datetime
    executed_at: Optional[datetime]
    error_message: Optional[str]

@dataclass
class AgentState:
    """Agent state model for tracking autonomous agent status."""
    id: Optional[int]
    last_perception_run: datetime
    last_decision_run: datetime
    last_action_run: datetime
    pools_monitored: int
    opportunities_detected: int
    trades_executed: int
    errors_count: int
    updated_at: datetime

@dataclass
class Opportunity:
    """Investment opportunity detected by the agent."""
    id: Optional[int]
    pool_id: str
    detected_at: datetime
    apr: float
    tvl: float
    risk_score: float
    confidence: float
    is_processed: bool
    users_notified: int

# Database schema definitions
SCHEMA_SQL = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

-- Subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'disabled',
    min_apr_threshold REAL DEFAULT 15.0,
    max_risk_level REAL DEFAULT 0.5,
    max_daily_investment REAL DEFAULT 1000.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

-- Pools table
CREATE TABLE IF NOT EXISTS pools (
    pool_id TEXT PRIMARY KEY,
    token_a TEXT NOT NULL,
    token_b TEXT NOT NULL,
    tvl REAL DEFAULT 0,
    volume_24h REAL DEFAULT 0,
    apy REAL DEFAULT 0,
    fee_rate REAL DEFAULT 0,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Trades table
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    pool_id TEXT NOT NULL,
    trade_type TEXT NOT NULL,
    input_token TEXT NOT NULL,
    output_token TEXT NOT NULL,
    input_amount REAL NOT NULL,
    output_amount REAL,
    slippage REAL DEFAULT 0,
    transaction_hash TEXT,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    executed_at DATETIME,
    error_message TEXT,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

-- Agent state table
CREATE TABLE IF NOT EXISTS agent_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_perception_run DATETIME,
    last_decision_run DATETIME,
    last_action_run DATETIME,
    pools_monitored INTEGER DEFAULT 0,
    opportunities_detected INTEGER DEFAULT 0,
    trades_executed INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Opportunities table
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id TEXT NOT NULL,
    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    apr REAL NOT NULL,
    tvl REAL NOT NULL,
    risk_score REAL DEFAULT 0,
    confidence REAL DEFAULT 0,
    is_processed BOOLEAN DEFAULT 0,
    users_notified INTEGER DEFAULT 0
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_pool_id ON opportunities(pool_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_detected_at ON opportunities(detected_at);
"""
