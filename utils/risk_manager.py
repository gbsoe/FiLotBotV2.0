"""
Risk management utilities for daily trading limits and exposure controls.
"""

from datetime import datetime, date
from typing import Optional
from loguru import logger
from utils.database import DatabaseManager


class RiskManager:
    """
    Risk management system for controlling user exposure and daily limits.
    """
    
    def __init__(self, db_manager: DatabaseManager, config):
        self.db_manager = db_manager
        self.config = config
    
    async def check_daily_limit(self, user_id: int, amount: float) -> bool:
        """
        Check if a user can make a trade within their daily limit.
        
        Args:
            user_id: User identifier
            amount: Proposed trade amount
            
        Returns:
            True if trade is within daily limit, False otherwise
        """
        try:
            today = date.today()
            
            # Get today's total trades for this user
            query = """
                SELECT COALESCE(SUM(input_amount), 0) as daily_total
                FROM trades 
                WHERE user_id = ? AND DATE(created_at) = ?
                AND status IN ('executed', 'pending')
            """
            
            async with self.db_manager.get_connection() as conn:
                cursor = await conn.execute(query, (user_id, today.isoformat()))
                result = await cursor.fetchone()
                daily_total = result['daily_total'] if result else 0.0
            
            # Get user's daily limit (default from config if not set)
            user_limit = await self._get_user_daily_limit(user_id)
            
            proposed_total = daily_total + amount
            
            if proposed_total > user_limit:
                logger.warning(f"Daily limit exceeded for user {user_id}: {proposed_total} > {user_limit}")
                return False
            
            logger.info(f"Daily limit check passed for user {user_id}: {proposed_total}/{user_limit}")
            return True
            
        except Exception as e:
            logger.error(f"Error checking daily limit for user {user_id}: {e}")
            return False  # Fail safe - reject if we can't verify
    
    async def _get_user_daily_limit(self, user_id: int) -> float:
        """
        Get user's daily limit from subscription settings or default.
        
        Args:
            user_id: User identifier
            
        Returns:
            Daily limit amount
        """
        try:
            query = """
                SELECT max_daily_investment 
                FROM subscriptions 
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
            """
            
            async with self.db_manager.get_connection() as conn:
                cursor = await conn.execute(query, (user_id,))
                result = await cursor.fetchone()
                
                if result and result['max_daily_investment']:
                    return float(result['max_daily_investment'])
                
                # Return default from config
                return getattr(self.config, 'MAX_DAILY_EXPOSURE_USD', 1000.0)
                
        except Exception as e:
            logger.error(f"Error getting daily limit for user {user_id}: {e}")
            return 1000.0  # Conservative default
    
    async def calculate_position_size(self, pool_data: dict, user_limit: float) -> float:
        """
        Calculate recommended position size based on pool risk and user limits.
        
        Args:
            pool_data: Pool information including TVL, volume, etc.
            user_limit: User's maximum investment amount
            
        Returns:
            Recommended position size
        """
        try:
            # Basic position sizing logic - TODO: enhance with more sophisticated risk metrics
            tvl = pool_data.get('tvl', 0)
            volume_24h = pool_data.get('volume24h', 0)
            
            # Risk score based on TVL and volume
            if tvl < 100000:  # Less than $100k TVL
                risk_multiplier = 0.1  # Very conservative
            elif tvl < 1000000:  # Less than $1M TVL
                risk_multiplier = 0.3
            else:
                risk_multiplier = 0.5  # Up to 50% of limit for large pools
            
            # Adjust for volume/TVL ratio (liquidity indicator)
            if tvl > 0:
                volume_ratio = volume_24h / tvl
                if volume_ratio > 0.5:  # High turnover
                    risk_multiplier *= 1.2  # Slightly more aggressive
                elif volume_ratio < 0.1:  # Low turnover
                    risk_multiplier *= 0.8  # More conservative
            
            recommended_size = min(user_limit * risk_multiplier, user_limit)
            
            logger.info(f"Calculated position size: {recommended_size} (limit: {user_limit}, multiplier: {risk_multiplier})")
            return recommended_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return min(100.0, user_limit * 0.1)  # Very conservative fallback
    
    async def assess_pool_risk(self, pool_data: dict) -> dict:
        """
        Assess risk level of a pool based on various metrics.
        
        Args:
            pool_data: Pool information
            
        Returns:
            Risk assessment dictionary
        """
        try:
            tvl = pool_data.get('tvl', 0)
            volume_24h = pool_data.get('volume24h', 0)
            apy = pool_data.get('apy', 0)
            
            risk_score = 0.0
            risk_factors = []
            
            # TVL-based risk
            if tvl < 100000:
                risk_score += 0.4
                risk_factors.append("Low TVL")
            elif tvl < 1000000:
                risk_score += 0.2
                risk_factors.append("Medium TVL")
            
            # APY-based risk (very high APY can indicate high risk)
            if apy > 100:
                risk_score += 0.3
                risk_factors.append("Very high APY")
            elif apy > 50:
                risk_score += 0.2
                risk_factors.append("High APY")
            
            # Volume/TVL ratio
            if tvl > 0:
                volume_ratio = volume_24h / tvl
                if volume_ratio < 0.05:  # Very low trading activity
                    risk_score += 0.2
                    risk_factors.append("Low liquidity")
            
            # Normalize risk score to 0-1 range
            risk_score = min(risk_score, 1.0)
            
            risk_level = "Low"
            if risk_score > 0.7:
                risk_level = "High"
            elif risk_score > 0.4:
                risk_level = "Medium"
            
            return {
                'risk_score': risk_score,
                'risk_level': risk_level,
                'risk_factors': risk_factors,
                'recommended': risk_score < 0.6
            }
            
        except Exception as e:
            logger.error(f"Error assessing pool risk: {e}")
            return {
                'risk_score': 1.0,
                'risk_level': "High",
                'risk_factors': ["Assessment failed"],
                'recommended': False
            }