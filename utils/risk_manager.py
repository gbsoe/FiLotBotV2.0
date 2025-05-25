"""
Risk management utilities for the trading bot.
Implements exposure limits, position sizing, and risk assessment.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
from models import Trade, Subscription, Pool
from utils.database import DatabaseManager

class RiskManager:
    """
    Manages trading risk through exposure limits and position sizing.
    """
    
    def __init__(self, db_manager: DatabaseManager, config):
        self.db_manager = db_manager
        self.config = config
    
    async def check_daily_exposure(self, user_id: int, proposed_amount: float) -> Tuple[bool, str]:
        """
        Check if a proposed trade would exceed daily exposure limits.
        
        Args:
            user_id: User ID
            proposed_amount: Proposed investment amount
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        try:
            current_exposure = await self.db_manager.get_user_daily_exposure(user_id)
            subscription = await self.db_manager.get_subscription(user_id)
            
            # Get user-specific limit or use default
            if subscription:
                daily_limit = subscription.max_daily_investment
            else:
                daily_limit = self.config.MAX_DAILY_EXPOSURE_USD
            
            total_exposure = current_exposure + proposed_amount
            
            if total_exposure > daily_limit:
                remaining = daily_limit - current_exposure
                return False, f"Daily limit exceeded. Current: ${current_exposure:.2f}, Limit: ${daily_limit:.2f}, Remaining: ${remaining:.2f}"
            
            return True, f"Within daily limit. Total exposure would be: ${total_exposure:.2f}/{daily_limit:.2f}"
            
        except Exception as e:
            logger.error(f"Error checking daily exposure: {e}")
            return False, "Unable to verify exposure limits"
    
    async def check_single_investment_limit(self, proposed_amount: float) -> Tuple[bool, str]:
        """
        Check if a single investment exceeds maximum limits.
        
        Args:
            proposed_amount: Proposed investment amount
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        max_single = self.config.MAX_SINGLE_INVESTMENT_USD
        
        if proposed_amount > max_single:
            return False, f"Single investment limit exceeded. Proposed: ${proposed_amount:.2f}, Max: ${max_single:.2f}"
        
        return True, f"Within single investment limit: ${proposed_amount:.2f}/{max_single:.2f}"
    
    async def assess_pool_risk(self, pool: Pool) -> Dict[str, float]:
        """
        Assess the risk level of a pool based on various metrics.
        
        Args:
            pool: Pool to assess
            
        Returns:
            Dictionary containing risk metrics
        """
        risk_metrics = {
            "tvl_risk": self._calculate_tvl_risk(pool.tvl),
            "volume_risk": self._calculate_volume_risk(pool.volume_24h, pool.tvl),
            "apy_risk": self._calculate_apy_risk(pool.apy),
            "overall_risk": 0.0
        }
        
        # Calculate weighted overall risk score (0-1, where 1 is highest risk)
        weights = {"tvl_risk": 0.4, "volume_risk": 0.3, "apy_risk": 0.3}
        
        risk_metrics["overall_risk"] = sum(
            risk_metrics[metric] * weight 
            for metric, weight in weights.items()
        )
        
        return risk_metrics
    
    def _calculate_tvl_risk(self, tvl: float) -> float:
        """Calculate risk based on Total Value Locked."""
        if tvl >= 10_000_000:  # $10M+
            return 0.1  # Very low risk
        elif tvl >= 1_000_000:  # $1M+
            return 0.3  # Low risk
        elif tvl >= 100_000:   # $100K+
            return 0.6  # Medium risk
        else:
            return 0.9  # High risk
    
    def _calculate_volume_risk(self, volume_24h: float, tvl: float) -> float:
        """Calculate risk based on trading volume relative to TVL."""
        if tvl == 0:
            return 1.0  # Maximum risk if no TVL
        
        volume_ratio = volume_24h / tvl
        
        if volume_ratio >= 0.5:    # High volume/TVL ratio
            return 0.2  # Low risk
        elif volume_ratio >= 0.1:  # Moderate volume
            return 0.4  # Medium-low risk
        elif volume_ratio >= 0.01: # Low volume
            return 0.7  # Medium-high risk
        else:
            return 0.9  # High risk (very low volume)
    
    def _calculate_apy_risk(self, apy: float) -> float:
        """Calculate risk based on APY (higher APY often means higher risk)."""
        if apy <= 5:      # Conservative yields
            return 0.2
        elif apy <= 15:   # Moderate yields
            return 0.4
        elif apy <= 50:   # High yields
            return 0.6
        elif apy <= 100:  # Very high yields
            return 0.8
        else:             # Extremely high yields
            return 1.0
    
    async def calculate_position_size(self, user_id: int, pool: Pool, 
                                    max_risk_level: float = 0.5) -> Optional[float]:
        """
        Calculate appropriate position size based on risk assessment.
        
        Args:
            user_id: User ID
            pool: Pool to invest in
            max_risk_level: Maximum acceptable risk level (0-1)
            
        Returns:
            Recommended position size in USD, or None if too risky
        """
        try:
            # Get user's subscription settings
            subscription = await self.db_manager.get_subscription(user_id)
            if not subscription:
                return None
            
            # Assess pool risk
            risk_metrics = await self.assess_pool_risk(pool)
            
            if risk_metrics["overall_risk"] > max_risk_level:
                logger.info(f"Pool {pool.pool_id} too risky: {risk_metrics['overall_risk']:.2f} > {max_risk_level}")
                return None
            
            # Calculate base position size
            base_size = subscription.max_daily_investment * 0.1  # Start with 10% of daily limit
            
            # Adjust based on risk (lower risk = larger position)
            risk_factor = 1.0 - risk_metrics["overall_risk"]
            adjusted_size = base_size * (0.5 + risk_factor * 0.5)  # Scale between 50-100% of base
            
            # Check against single investment limit
            max_single = self.config.MAX_SINGLE_INVESTMENT_USD
            final_size = min(adjusted_size, max_single)
            
            # Check daily exposure
            current_exposure = await self.db_manager.get_user_daily_exposure(user_id)
            remaining_exposure = subscription.max_daily_investment - current_exposure
            
            if final_size > remaining_exposure:
                final_size = max(0, remaining_exposure)
            
            logger.info(f"Calculated position size for {pool.pool_id}: ${final_size:.2f} (risk: {risk_metrics['overall_risk']:.2f})")
            return final_size if final_size > 10 else None  # Minimum $10 investment
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return None
    
    async def should_execute_trade(self, user_id: int, pool: Pool, amount: float) -> Tuple[bool, str]:
        """
        Comprehensive check if a trade should be executed.
        
        Args:
            user_id: User ID
            pool: Pool to trade
            amount: Investment amount
            
        Returns:
            Tuple of (should_execute, reason)
        """
        # Check single investment limit
        single_check, single_reason = await self.check_single_investment_limit(amount)
        if not single_check:
            return False, single_reason
        
        # Check daily exposure
        exposure_check, exposure_reason = await self.check_daily_exposure(user_id, amount)
        if not exposure_check:
            return False, exposure_reason
        
        # Assess pool risk
        risk_metrics = await self.assess_pool_risk(pool)
        subscription = await self.db_manager.get_subscription(user_id)
        
        if subscription and risk_metrics["overall_risk"] > subscription.max_risk_level:
            return False, f"Pool risk too high: {risk_metrics['overall_risk']:.2f} > {subscription.max_risk_level:.2f}"
        
        # All checks passed
        return True, f"Trade approved. Risk: {risk_metrics['overall_risk']:.2f}, Amount: ${amount:.2f}"
