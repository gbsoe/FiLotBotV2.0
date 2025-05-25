"""
Configuration management for the Telegram bot.
Loads settings from environment variables with fallbacks.
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration class for the bot."""
    
    def __init__(self):
        # Required environment variables
        self.TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
        self.FILOT_BASE_URL: str = os.getenv("FILOT_BASE_URL", "https://api.filot.io")
        self.SOLANA_PRIVATE_KEY: str = os.getenv("SOLANA_PRIVATE_KEY", "")
        
        # Optional environment variables
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        
        # Database configuration
        self.DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot_data.db")
        
        # Agent configuration
        self.MONITORING_INTERVAL: int = int(os.getenv("MONITORING_INTERVAL", "10800"))  # 3 hours
        self.MIN_APR_THRESHOLD: float = float(os.getenv("MIN_APR_THRESHOLD", "15.0"))
        self.MIN_TVL_THRESHOLD: float = float(os.getenv("MIN_TVL_THRESHOLD", "1000000"))  # $1M
        self.MAX_SLIPPAGE: float = float(os.getenv("MAX_SLIPPAGE", "5.0"))
        
        # Risk management
        self.MAX_DAILY_EXPOSURE_USD: float = float(os.getenv("MAX_DAILY_EXPOSURE_USD", "10000"))
        self.MAX_SINGLE_INVESTMENT_USD: float = float(os.getenv("MAX_SINGLE_INVESTMENT_USD", "1000"))
        
        # Validate required configuration
        self._validate_config()
    
    def _validate_config(self):
        """Validate required configuration parameters."""
        if not self.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN environment variable is required")
        if not self.SOLANA_PRIVATE_KEY:
            raise ValueError("SOLANA_PRIVATE_KEY environment variable is required")
    
    @property
    def is_openai_enabled(self) -> bool:
        """Check if OpenAI integration is available."""
        return bool(self.OPENAI_API_KEY)
