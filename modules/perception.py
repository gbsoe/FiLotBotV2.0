"""
Perception module for the autonomous agent.
Gathers market data, analyzes pools, and prepares data for decision making.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger

from config import Config
from utils.database import DatabaseManager
from utils.filot_client import FiLotClient, FiLotError
from models import Pool

class PerceptionModule:
    """
    Handles data gathering and market perception for the autonomous agent.
    """
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
    
    async def run(self) -> Dict[str, Any]:
        """
        Main perception cycle: gather and analyze market data.
        
        Returns:
            Dictionary containing perception results:
            - pools: List of analyzed pools
            - market_metrics: Overall market indicators
            - opportunities: Preliminary opportunity detection
            - timestamp: When the data was gathered
        """
        perception_start = datetime.now()
        logger.info("🔍 Starting perception module")
        
        try:
            # 1. Fetch current pool data from FiLot API
            pools_data = await self._fetch_pools_data()
            
            # 2. Analyze and filter pools
            analyzed_pools = await self._analyze_pools(pools_data)
            
            # 3. Calculate market metrics
            market_metrics = await self._calculate_market_metrics(analyzed_pools)
            
            # 4. Detect preliminary opportunities
            opportunities = await self._detect_opportunities(analyzed_pools, market_metrics)
            
            # 5. Update pool data in database
            await self._update_pool_database(analyzed_pools)
            
            perception_duration = (datetime.now() - perception_start).total_seconds()
            
            result = {
                'pools': analyzed_pools,
                'market_metrics': market_metrics,
                'opportunities': opportunities,
                'timestamp': datetime.now(),
                'processing_time': perception_duration,
                'pools_fetched': len(pools_data),
                'pools_analyzed': len(analyzed_pools)
            }
            
            logger.info(f"✅ Perception completed: {len(analyzed_pools)} pools analyzed in {perception_duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error in perception module: {e}")
            return {
                'pools': [],
                'market_metrics': {},
                'opportunities': [],
                'timestamp': datetime.now(),
                'error': str(e)
            }
    
    async def _fetch_pools_data(self) -> List[Dict[str, Any]]:
        """Fetch fresh pool data from FiLot API."""
        try:
            async with FiLotClient(self.config) as client:
                pools_data = await client.get_pools()
            
            logger.debug(f"Fetched {len(pools_data)} pools from API")
            return pools_data
            
        except FiLotError as e:
            logger.error(f"FiLot API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching pools: {e}")
            raise
    
    async def _analyze_pools(self, pools_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze pools and add calculated metrics.
        
        Args:
            pools_data: Raw pool data from API
            
        Returns:
            Enhanced pool data with analysis metrics
        """
        analyzed_pools = []
        
        for pool_data in pools_data:
            try:
                # Extract basic pool info
                pool_id = pool_data.get('poolId', '')
                token_a = pool_data.get('tokenA', '')
                token_b = pool_data.get('tokenB', '')
                tvl = float(pool_data.get('tvl', 0))
                volume_24h = float(pool_data.get('volume24h', 0))
                apy = float(pool_data.get('apy', 0))
                fee_rate = float(pool_data.get('feeRate', 0))
                
                # Skip pools with insufficient data
                if not all([pool_id, token_a, token_b]) or tvl <= 0:
                    continue
                
                # Calculate derived metrics
                volume_to_tvl_ratio = volume_24h / tvl if tvl > 0 else 0
                liquidity_score = self._calculate_liquidity_score(tvl, volume_24h)
                stability_score = self._calculate_stability_score(apy, volume_to_tvl_ratio)
                
                # Fetch additional metrics if available
                additional_metrics = await self._fetch_additional_metrics(pool_id)
                
                # Create enhanced pool data
                enhanced_pool = {
                    'pool_id': pool_id,
                    'token_a': token_a,
                    'token_b': token_b,
                    'tvl': tvl,
                    'volume_24h': volume_24h,
                    'apy': apy,
                    'fee_rate': fee_rate,
                    'volume_to_tvl_ratio': volume_to_tvl_ratio,
                    'liquidity_score': liquidity_score,
                    'stability_score': stability_score,
                    'analysis_timestamp': datetime.now(),
                    **additional_metrics
                }
                
                analyzed_pools.append(enhanced_pool)
                
            except Exception as e:
                logger.warning(f"Error analyzing pool {pool_data.get('poolId', 'unknown')}: {e}")
                continue
        
        logger.debug(f"Successfully analyzed {len(analyzed_pools)} pools")
        return analyzed_pools
    
    async def _fetch_additional_metrics(self, pool_id: str) -> Dict[str, Any]:
        """Fetch additional metrics for a specific pool."""
        try:
            async with FiLotClient(self.config) as client:
                metrics_data = await client.get_pool_metrics(pool_id, timeframe="24h")
            
            return {
                'price_change_24h': metrics_data.get('priceChange24h', 0),
                'volume_change_24h': metrics_data.get('volumeChange24h', 0),
                'liquidity_change_24h': metrics_data.get('liquidityChange24h', 0),
                'fee_revenue_24h': metrics_data.get('feeRevenue24h', 0),
                'active_traders_24h': metrics_data.get('activeTraders24h', 0)
            }
            
        except Exception:
            # Return empty metrics if fetch fails
            return {
                'price_change_24h': 0,
                'volume_change_24h': 0,
                'liquidity_change_24h': 0,
                'fee_revenue_24h': 0,
                'active_traders_24h': 0
            }
    
    def _calculate_liquidity_score(self, tvl: float, volume_24h: float) -> float:
        """
        Calculate a liquidity score (0-1) based on TVL and volume.
        Higher score indicates better liquidity.
        """
        # Base score from TVL
        if tvl >= 50_000_000:  # $50M+
            tvl_score = 1.0
        elif tvl >= 10_000_000:  # $10M+
            tvl_score = 0.8
        elif tvl >= 1_000_000:   # $1M+
            tvl_score = 0.6
        elif tvl >= 100_000:     # $100K+
            tvl_score = 0.4
        else:
            tvl_score = 0.2
        
        # Volume activity score
        volume_ratio = volume_24h / tvl if tvl > 0 else 0
        if volume_ratio >= 1.0:      # High activity
            volume_score = 1.0
        elif volume_ratio >= 0.5:    # Good activity
            volume_score = 0.8
        elif volume_ratio >= 0.1:    # Moderate activity
            volume_score = 0.6
        elif volume_ratio >= 0.01:   # Low activity
            volume_score = 0.4
        else:
            volume_score = 0.2
        
        # Weighted combination
        return (tvl_score * 0.7) + (volume_score * 0.3)
    
    def _calculate_stability_score(self, apy: float, volume_ratio: float) -> float:
        """
        Calculate a stability score (0-1) based on APY and activity.
        Higher score indicates more stable/sustainable returns.
        """
        # APY sustainability score (very high APY is often unsustainable)
        if 5 <= apy <= 25:          # Sweet spot
            apy_score = 1.0
        elif 25 < apy <= 50:        # High but potentially sustainable
            apy_score = 0.8
        elif 1 <= apy < 5:          # Conservative
            apy_score = 0.7
        elif 50 < apy <= 100:       # Very high risk
            apy_score = 0.4
        else:                       # Extreme (either too low or too high)
            apy_score = 0.2
        
        # Volume stability score
        if 0.1 <= volume_ratio <= 2.0:  # Healthy range
            volume_score = 1.0
        elif 0.05 <= volume_ratio < 0.1 or 2.0 < volume_ratio <= 5.0:
            volume_score = 0.7
        else:
            volume_score = 0.3
        
        return (apy_score * 0.6) + (volume_score * 0.4)
    
    async def _calculate_market_metrics(self, pools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall market metrics from analyzed pools."""
        if not pools:
            return {}
        
        try:
            total_tvl = sum(pool['tvl'] for pool in pools)
            total_volume = sum(pool['volume_24h'] for pool in pools)
            avg_apy = sum(pool['apy'] for pool in pools) / len(pools)
            
            # APY distribution
            high_apy_pools = len([p for p in pools if p['apy'] >= self.config.MIN_APR_THRESHOLD])
            medium_apy_pools = len([p for p in pools if 5 <= p['apy'] < self.config.MIN_APR_THRESHOLD])
            low_apy_pools = len([p for p in pools if p['apy'] < 5])
            
            # Liquidity distribution
            high_liquidity_pools = len([p for p in pools if p['liquidity_score'] >= 0.7])
            stable_pools = len([p for p in pools if p['stability_score'] >= 0.7])
            
            return {
                'total_pools': len(pools),
                'total_tvl': total_tvl,
                'total_volume_24h': total_volume,
                'avg_apy': avg_apy,
                'market_volume_ratio': total_volume / total_tvl if total_tvl > 0 else 0,
                'high_apy_pools': high_apy_pools,
                'medium_apy_pools': medium_apy_pools,
                'low_apy_pools': low_apy_pools,
                'high_liquidity_pools': high_liquidity_pools,
                'stable_pools': stable_pools,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error calculating market metrics: {e}")
            return {}
    
    async def _detect_opportunities(self, pools: List[Dict[str, Any]], 
                                  market_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect preliminary investment opportunities.
        This is basic filtering - detailed analysis happens in decision module.
        """
        opportunities = []
        
        try:
            for pool in pools:
                # Basic criteria for opportunity detection
                meets_apy_threshold = pool['apy'] >= self.config.MIN_APR_THRESHOLD
                meets_tvl_threshold = pool['tvl'] >= self.config.MIN_TVL_THRESHOLD
                good_liquidity = pool['liquidity_score'] >= 0.5
                reasonable_stability = pool['stability_score'] >= 0.4
                
                if all([meets_apy_threshold, meets_tvl_threshold, good_liquidity, reasonable_stability]):
                    opportunity = {
                        'pool_id': pool['pool_id'],
                        'token_pair': f"{pool['token_a']}/{pool['token_b']}",
                        'apy': pool['apy'],
                        'tvl': pool['tvl'],
                        'liquidity_score': pool['liquidity_score'],
                        'stability_score': pool['stability_score'],
                        'opportunity_score': self._calculate_opportunity_score(pool),
                        'detected_at': datetime.now()
                    }
                    opportunities.append(opportunity)
            
            # Sort by opportunity score
            opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)
            
            logger.info(f"Detected {len(opportunities)} preliminary opportunities")
            return opportunities
            
        except Exception as e:
            logger.error(f"Error detecting opportunities: {e}")
            return []
    
    def _calculate_opportunity_score(self, pool: Dict[str, Any]) -> float:
        """
        Calculate a composite opportunity score (0-1).
        Higher score indicates better opportunity.
        """
        try:
            # Normalize APY (cap at 100% for scoring)
            apy_score = min(pool['apy'] / 100.0, 1.0)
            
            # Get pre-calculated scores
            liquidity_score = pool['liquidity_score']
            stability_score = pool['stability_score']
            
            # Volume activity bonus
            volume_ratio = pool.get('volume_to_tvl_ratio', 0)
            activity_bonus = min(volume_ratio, 1.0) * 0.1
            
            # Weighted combination
            opportunity_score = (
                apy_score * 0.4 +           # APY is important but not everything
                liquidity_score * 0.3 +     # Liquidity for execution
                stability_score * 0.2 +     # Sustainability
                activity_bonus              # Activity bonus
            )
            
            return min(opportunity_score, 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating opportunity score: {e}")
            return 0.0
    
    async def _update_pool_database(self, pools: List[Dict[str, Any]]):
        """Update pool data in the database."""
        try:
            for pool_data in pools:
                pool = Pool(
                    pool_id=pool_data['pool_id'],
                    token_a=pool_data['token_a'],
                    token_b=pool_data['token_b'],
                    tvl=pool_data['tvl'],
                    volume_24h=pool_data['volume_24h'],
                    apy=pool_data['apy'],
                    fee_rate=pool_data['fee_rate'],
                    last_updated=datetime.now()
                )
                
                await self.db_manager.update_pool(pool)
            
            logger.debug(f"Updated {len(pools)} pools in database")
            
        except Exception as e:
            logger.error(f"Error updating pool database: {e}")
