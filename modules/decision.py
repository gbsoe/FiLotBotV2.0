"""
Decision module for the autonomous agent.
Analyzes perception data and makes intelligent trading decisions.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from config import Config
from utils.database import DatabaseManager
from utils.risk_manager import RiskManager
from models import Subscription, SubscriptionStatus, Pool, Opportunity

class DecisionModule:
    """
    Handles intelligent decision making for autonomous trading.
    Implements rule-based triggers with hooks for future ML integration.
    """
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.risk_manager = RiskManager(db_manager, config)
    
    async def run(self, perception_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main decision cycle: analyze perception data and make trading decisions.
        
        Args:
            perception_data: Output from perception module
            
        Returns:
            Dictionary containing decision results:
            - opportunities: Validated investment opportunities
            - notifications: Users to notify about opportunities
            - actions: Specific actions to take
            - reasoning: Decision reasoning for each opportunity
        """
        decision_start = datetime.now()
        logger.info("🧠 Starting decision module")
        
        try:
            # Extract data from perception
            pools = perception_data.get('pools', [])
            market_metrics = perception_data.get('market_metrics', {})
            preliminary_opportunities = perception_data.get('opportunities', [])
            
            if not pools:
                logger.warning("No pool data available for decision making")
                return self._empty_decision_result()
            
            # 1. Get active subscriptions
            active_subscriptions = await self.db_manager.get_active_subscriptions()
            
            if not active_subscriptions:
                logger.info("No active subscriptions for autonomous trading")
                return self._empty_decision_result()
            
            # 2. Analyze opportunities against decision criteria
            validated_opportunities = await self._validate_opportunities(
                preliminary_opportunities, pools, market_metrics
            )
            
            # 3. Apply user-specific decision logic
            user_decisions = await self._make_user_decisions(
                validated_opportunities, active_subscriptions, pools
            )
            
            # 4. Risk management and position sizing
            final_decisions = await self._apply_risk_management(user_decisions)
            
            # 5. Generate notification targets
            notifications = await self._generate_notifications(final_decisions)
            
            decision_duration = (datetime.now() - decision_start).total_seconds()
            
            result = {
                'opportunities': final_decisions,
                'notifications': notifications,
                'actions': await self._generate_actions(final_decisions),
                'reasoning': await self._generate_reasoning(final_decisions),
                'market_analysis': await self._analyze_market_conditions(market_metrics),
                'timestamp': datetime.now(),
                'processing_time': decision_duration,
                'users_analyzed': len(active_subscriptions),
                'opportunities_validated': len(validated_opportunities)
            }
            
            logger.info(f"✅ Decision completed: {len(final_decisions)} final opportunities in {decision_duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error in decision module: {e}")
            return {
                'opportunities': [],
                'notifications': [],
                'actions': [],
                'reasoning': {},
                'timestamp': datetime.now(),
                'error': str(e)
            }
    
    def _empty_decision_result(self) -> Dict[str, Any]:
        """Return empty decision result structure."""
        return {
            'opportunities': [],
            'notifications': [],
            'actions': [],
            'reasoning': {},
            'market_analysis': {},
            'timestamp': datetime.now(),
            'processing_time': 0,
            'users_analyzed': 0,
            'opportunities_validated': 0
        }
    
    async def _validate_opportunities(self, preliminary_opportunities: List[Dict[str, Any]], 
                                    pools: List[Dict[str, Any]], 
                                    market_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Validate preliminary opportunities against detailed criteria.
        
        Args:
            preliminary_opportunities: Opportunities from perception module
            pools: Full pool data
            market_metrics: Market condition metrics
            
        Returns:
            List of validated opportunities with enhanced analysis
        """
        validated = []
        
        try:
            for opportunity in preliminary_opportunities:
                pool_id = opportunity['pool_id']
                
                # Find full pool data
                pool_data = next((p for p in pools if p['pool_id'] == pool_id), None)
                if not pool_data:
                    continue
                
                # Create Pool object for risk assessment
                pool_obj = Pool(
                    pool_id=pool_id,
                    token_a=pool_data['token_a'],
                    token_b=pool_data['token_b'],
                    tvl=pool_data['tvl'],
                    volume_24h=pool_data['volume_24h'],
                    apy=pool_data['apy'],
                    fee_rate=pool_data['fee_rate'],
                    last_updated=datetime.now()
                )
                
                # Detailed risk assessment
                risk_metrics = await self.risk_manager.assess_pool_risk(pool_obj)
                
                # Market context analysis
                market_context = self._analyze_pool_market_context(pool_data, market_metrics)
                
                # Decision triggers
                triggers = self._evaluate_decision_triggers(pool_data, risk_metrics, market_context)
                
                if triggers['should_recommend']:
                    enhanced_opportunity = {
                        **opportunity,
                        'risk_metrics': risk_metrics,
                        'market_context': market_context,
                        'triggers': triggers,
                        'confidence_score': self._calculate_confidence_score(
                            pool_data, risk_metrics, market_context
                        ),
                        'urgency_level': self._calculate_urgency_level(pool_data, market_context),
                        'validated_at': datetime.now()
                    }
                    
                    validated.append(enhanced_opportunity)
            
            logger.info(f"Validated {len(validated)}/{len(preliminary_opportunities)} opportunities")
            return validated
            
        except Exception as e:
            logger.error(f"Error validating opportunities: {e}")
            return []
    
    def _analyze_pool_market_context(self, pool_data: Dict[str, Any], 
                                   market_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze pool performance relative to market conditions."""
        try:
            pool_apy = pool_data['apy']
            pool_tvl = pool_data['tvl']
            pool_volume_ratio = pool_data.get('volume_to_tvl_ratio', 0)
            
            market_avg_apy = market_metrics.get('avg_apy', 0)
            total_market_tvl = market_metrics.get('total_tvl', 1)
            
            return {
                'apy_vs_market': pool_apy / market_avg_apy if market_avg_apy > 0 else 1,
                'tvl_market_share': pool_tvl / total_market_tvl if total_market_tvl > 0 else 0,
                'volume_percentile': self._calculate_volume_percentile(pool_volume_ratio),
                'is_trending_up': pool_data.get('volume_change_24h', 0) > 0,
                'price_stability': abs(pool_data.get('price_change_24h', 0)) < 5,  # Less than 5% change
                'liquidity_growth': pool_data.get('liquidity_change_24h', 0) > 0
            }
            
        except Exception as e:
            logger.warning(f"Error analyzing market context: {e}")
            return {}
    
    def _calculate_volume_percentile(self, volume_ratio: float) -> float:
        """Calculate approximate volume percentile (0-1)."""
        # Simple heuristic based on typical DeFi volume ratios
        if volume_ratio >= 2.0:
            return 0.95
        elif volume_ratio >= 1.0:
            return 0.85
        elif volume_ratio >= 0.5:
            return 0.70
        elif volume_ratio >= 0.1:
            return 0.50
        elif volume_ratio >= 0.05:
            return 0.30
        else:
            return 0.15
    
    def _evaluate_decision_triggers(self, pool_data: Dict[str, Any], 
                                  risk_metrics: Dict[str, Any], 
                                  market_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate rule-based decision triggers.
        
        Returns:
            Dictionary with trigger results and reasoning
        """
        triggers = {
            'should_recommend': False,
            'trigger_reasons': [],
            'warning_flags': []
        }
        
        try:
            apy = pool_data['apy']
            tvl = pool_data['tvl']
            overall_risk = risk_metrics.get('overall_risk', 1.0)
            
            # Core triggers
            high_apy_trigger = apy >= self.config.MIN_APR_THRESHOLD
            sufficient_tvl_trigger = tvl >= self.config.MIN_TVL_THRESHOLD
            acceptable_risk_trigger = overall_risk <= 0.7  # Max 70% risk
            
            # Market context triggers
            above_market_apy = market_context.get('apy_vs_market', 0) > 1.2  # 20% above market
            good_liquidity = pool_data.get('liquidity_score', 0) >= 0.6
            stable_price = market_context.get('price_stability', False)
            
            # Advanced triggers
            volume_activity = pool_data.get('volume_to_tvl_ratio', 0) >= 0.1
            growing_liquidity = market_context.get('liquidity_growth', False)
            
            # Evaluate triggers
            core_triggers_met = all([high_apy_trigger, sufficient_tvl_trigger, acceptable_risk_trigger])
            
            if core_triggers_met:
                triggers['trigger_reasons'].append(f"Core criteria met: {apy:.1f}% APY, ${tvl:,.0f} TVL, {overall_risk:.2f} risk")
                
                # Additional positive signals
                if above_market_apy:
                    triggers['trigger_reasons'].append(f"APY {market_context.get('apy_vs_market', 1):.1f}x above market average")
                
                if good_liquidity and volume_activity:
                    triggers['trigger_reasons'].append("Strong liquidity and trading activity")
                
                if stable_price and growing_liquidity:
                    triggers['trigger_reasons'].append("Price stable with growing liquidity")
                
                # Check for warning flags
                if overall_risk > 0.5:
                    triggers['warning_flags'].append(f"Elevated risk level: {overall_risk:.2f}")
                
                if apy > 100:
                    triggers['warning_flags'].append(f"Very high APY may be unsustainable: {apy:.1f}%")
                
                if not stable_price:
                    triggers['warning_flags'].append("Price volatility detected")
                
                # Final decision
                warning_count = len(triggers['warning_flags'])
                positive_signals = len(triggers['trigger_reasons']) - 1  # Exclude core trigger
                
                # Recommend if core triggers met and benefits outweigh risks
                triggers['should_recommend'] = warning_count <= positive_signals
                
            else:
                # Identify which core triggers failed
                if not high_apy_trigger:
                    triggers['warning_flags'].append(f"APY below threshold: {apy:.1f}% < {self.config.MIN_APR_THRESHOLD}%")
                if not sufficient_tvl_trigger:
                    triggers['warning_flags'].append(f"TVL below threshold: ${tvl:,.0f} < ${self.config.MIN_TVL_THRESHOLD:,.0f}")
                if not acceptable_risk_trigger:
                    triggers['warning_flags'].append(f"Risk too high: {overall_risk:.2f} > 0.7")
            
            return triggers
            
        except Exception as e:
            logger.error(f"Error evaluating triggers: {e}")
            return {'should_recommend': False, 'trigger_reasons': [], 'warning_flags': [f"Evaluation error: {e}"]}
    
    def _calculate_confidence_score(self, pool_data: Dict[str, Any], 
                                  risk_metrics: Dict[str, Any], 
                                  market_context: Dict[str, Any]) -> float:
        """Calculate confidence score (0-1) for the opportunity."""
        try:
            # Base confidence from pool metrics
            liquidity_confidence = pool_data.get('liquidity_score', 0) * 0.3
            stability_confidence = pool_data.get('stability_score', 0) * 0.2
            
            # Risk-adjusted confidence
            risk_confidence = (1.0 - risk_metrics.get('overall_risk', 1.0)) * 0.2
            
            # Market context confidence
            market_confidence = 0
            if market_context.get('apy_vs_market', 0) > 1:
                market_confidence += 0.1
            if market_context.get('price_stability', False):
                market_confidence += 0.1
            if market_context.get('liquidity_growth', False):
                market_confidence += 0.1
            
            total_confidence = liquidity_confidence + stability_confidence + risk_confidence + market_confidence
            return min(total_confidence, 1.0)
            
        except Exception:
            return 0.5  # Default medium confidence
    
    def _calculate_urgency_level(self, pool_data: Dict[str, Any], 
                               market_context: Dict[str, Any]) -> str:
        """Calculate urgency level for the opportunity."""
        try:
            apy = pool_data['apy']
            volume_change = pool_data.get('volume_change_24h', 0)
            liquidity_change = pool_data.get('liquidity_change_24h', 0)
            
            # High urgency conditions
            if apy >= 50 and volume_change > 20:
                return "high"
            
            # Medium urgency conditions
            if apy >= 25 or (volume_change > 10 and liquidity_change > 5):
                return "medium"
            
            # Low urgency (normal opportunities)
            return "low"
            
        except Exception:
            return "low"
    
    async def _make_user_decisions(self, opportunities: List[Dict[str, Any]], 
                                 subscriptions: List[Subscription], 
                                 pools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply user-specific decision logic to opportunities.
        
        Args:
            opportunities: Validated opportunities
            subscriptions: Active user subscriptions
            pools: Full pool data
            
        Returns:
            List of user-specific investment decisions
        """
        user_decisions = []
        
        try:
            for subscription in subscriptions:
                user_id = subscription.user_id
                
                # Check user's daily exposure
                current_exposure = await self.db_manager.get_user_daily_exposure(user_id)
                remaining_budget = subscription.max_daily_investment - current_exposure
                
                if remaining_budget <= 10:  # Minimum $10 investment
                    logger.debug(f"User {user_id} has insufficient remaining budget: ${remaining_budget:.2f}")
                    continue
                
                # Filter opportunities by user preferences
                user_opportunities = []
                for opportunity in opportunities:
                    # Check APY threshold
                    if opportunity['apy'] < subscription.min_apr_threshold:
                        continue
                    
                    # Check risk tolerance
                    if opportunity['risk_metrics']['overall_risk'] > subscription.max_risk_level:
                        continue
                    
                    # Calculate position size for this user
                    pool_data = next((p for p in pools if p['pool_id'] == opportunity['pool_id']), None)
                    if not pool_data:
                        continue
                    
                    pool_obj = Pool(
                        pool_id=opportunity['pool_id'],
                        token_a=pool_data['token_a'],
                        token_b=pool_data['token_b'],
                        tvl=pool_data['tvl'],
                        volume_24h=pool_data['volume_24h'],
                        apy=pool_data['apy'],
                        fee_rate=pool_data['fee_rate'],
                        last_updated=datetime.now()
                    )
                    
                    suggested_amount = await self.risk_manager.calculate_position_size(
                        user_id, pool_obj, subscription.max_risk_level
                    )
                    
                    if suggested_amount and suggested_amount <= remaining_budget:
                        user_opportunity = {
                            **opportunity,
                            'user_id': user_id,
                            'suggested_amount': suggested_amount,
                            'user_risk_tolerance': subscription.max_risk_level,
                            'user_apy_threshold': subscription.min_apr_threshold,
                            'remaining_budget': remaining_budget,
                            'decision_timestamp': datetime.now()
                        }
                        user_opportunities.append(user_opportunity)
                
                # Sort by opportunity score and take top opportunities
                user_opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)
                
                # Limit to top 3 opportunities per user to avoid spam
                for opportunity in user_opportunities[:3]:
                    user_decisions.append(opportunity)
            
            logger.info(f"Generated {len(user_decisions)} user-specific decisions")
            return user_decisions
            
        except Exception as e:
            logger.error(f"Error making user decisions: {e}")
            return []
    
    async def _apply_risk_management(self, user_decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply final risk management checks to user decisions."""
        final_decisions = []
        
        try:
            for decision in user_decisions:
                user_id = decision['user_id']
                pool_id = decision['pool_id']
                suggested_amount = decision['suggested_amount']
                
                # Final risk validation
                pool_obj = Pool(
                    pool_id=pool_id,
                    token_a=decision['token_a'],
                    token_b=decision['token_b'],
                    tvl=decision['tvl'],
                    volume_24h=decision['volume_24h'],
                    apy=decision['apy'],
                    fee_rate=decision.get('fee_rate', 0),
                    last_updated=datetime.now()
                )
                
                can_execute, risk_reason = await self.risk_manager.should_execute_trade(
                    user_id, pool_obj, suggested_amount
                )
                
                if can_execute:
                    decision['risk_approved'] = True
                    decision['risk_reason'] = risk_reason
                    final_decisions.append(decision)
                else:
                    logger.debug(f"Risk management blocked decision for user {user_id}: {risk_reason}")
            
            logger.info(f"Risk management approved {len(final_decisions)}/{len(user_decisions)} decisions")
            return final_decisions
            
        except Exception as e:
            logger.error(f"Error in risk management: {e}")
            return []
    
    async def _generate_notifications(self, decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate notification targets for approved decisions."""
        notifications = []
        
        try:
            # Group decisions by user
            user_decisions = {}
            for decision in decisions:
                user_id = decision['user_id']
                if user_id not in user_decisions:
                    user_decisions[user_id] = []
                user_decisions[user_id].append(decision)
            
            # Create notifications
            for user_id, user_decision_list in user_decisions.items():
                # Sort by urgency and opportunity score
                user_decision_list.sort(
                    key=lambda x: (
                        {'high': 3, 'medium': 2, 'low': 1}[x['urgency_level']],
                        x['opportunity_score']
                    ),
                    reverse=True
                )
                
                notification = {
                    'user_id': user_id,
                    'decisions': user_decision_list,
                    'priority': user_decision_list[0]['urgency_level'],
                    'total_opportunities': len(user_decision_list),
                    'best_apy': max(d['apy'] for d in user_decision_list),
                    'total_potential_investment': sum(d['suggested_amount'] for d in user_decision_list),
                    'notification_type': 'opportunity_alert',
                    'created_at': datetime.now()
                }
                
                notifications.append(notification)
            
            return notifications
            
        except Exception as e:
            logger.error(f"Error generating notifications: {e}")
            return []
    
    async def _generate_actions(self, decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate specific actions to be taken by the action module."""
        actions = []
        
        try:
            for decision in decisions:
                # Action for notification
                actions.append({
                    'type': 'send_notification',
                    'user_id': decision['user_id'],
                    'pool_id': decision['pool_id'],
                    'suggested_amount': decision['suggested_amount'],
                    'urgency': decision['urgency_level'],
                    'confidence': decision['confidence_score']
                })
                
                # Record opportunity in database
                actions.append({
                    'type': 'record_opportunity',
                    'pool_id': decision['pool_id'],
                    'apy': decision['apy'],
                    'tvl': decision['tvl'],
                    'risk_score': decision['risk_metrics']['overall_risk'],
                    'confidence': decision['confidence_score']
                })
            
            return actions
            
        except Exception as e:
            logger.error(f"Error generating actions: {e}")
            return []
    
    async def _generate_reasoning(self, decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate human-readable reasoning for decisions."""
        reasoning = {
            'total_decisions': len(decisions),
            'decision_summary': {},
            'risk_analysis': {},
            'market_insights': []
        }
        
        try:
            if not decisions:
                reasoning['decision_summary'] = "No investment opportunities met all criteria"
                return reasoning
            
            # Summarize decisions
            apys = [d['apy'] for d in decisions]
            risk_scores = [d['risk_metrics']['overall_risk'] for d in decisions]
            
            reasoning['decision_summary'] = {
                'opportunities_found': len(decisions),
                'avg_apy': sum(apys) / len(apys),
                'apy_range': f"{min(apys):.1f}% - {max(apys):.1f}%",
                'avg_risk': sum(risk_scores) / len(risk_scores),
                'risk_range': f"{min(risk_scores):.2f} - {max(risk_scores):.2f}"
            }
            
            # Risk analysis
            low_risk = len([d for d in decisions if d['risk_metrics']['overall_risk'] <= 0.3])
            medium_risk = len([d for d in decisions if 0.3 < d['risk_metrics']['overall_risk'] <= 0.6])
            high_risk = len([d for d in decisions if d['risk_metrics']['overall_risk'] > 0.6])
            
            reasoning['risk_analysis'] = {
                'low_risk_opportunities': low_risk,
                'medium_risk_opportunities': medium_risk,
                'high_risk_opportunities': high_risk
            }
            
            # Market insights
            high_urgency = len([d for d in decisions if d['urgency_level'] == 'high'])
            if high_urgency > 0:
                reasoning['market_insights'].append(f"{high_urgency} high-urgency opportunities detected")
            
            above_market = len([d for d in decisions if d.get('market_context', {}).get('apy_vs_market', 0) > 1.5])
            if above_market > 0:
                reasoning['market_insights'].append(f"{above_market} opportunities significantly above market average")
            
            return reasoning
            
        except Exception as e:
            logger.error(f"Error generating reasoning: {e}")
            return reasoning
    
    async def _analyze_market_conditions(self, market_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze overall market conditions for decision context."""
        try:
            analysis = {
                'market_health': 'unknown',
                'total_opportunities': market_metrics.get('high_apy_pools', 0),
                'market_liquidity': 'unknown',
                'recommendations': []
            }
            
            total_tvl = market_metrics.get('total_tvl', 0)
            avg_apy = market_metrics.get('avg_apy', 0)
            high_liquidity_pools = market_metrics.get('high_liquidity_pools', 0)
            stable_pools = market_metrics.get('stable_pools', 0)
            total_pools = market_metrics.get('total_pools', 1)
            
            # Market health assessment
            if avg_apy >= 20 and stable_pools / total_pools >= 0.3:
                analysis['market_health'] = 'excellent'
                analysis['recommendations'].append("Strong market conditions favor aggressive investment")
            elif avg_apy >= 10 and stable_pools / total_pools >= 0.2:
                analysis['market_health'] = 'good'
                analysis['recommendations'].append("Favorable conditions for moderate investment")
            elif avg_apy >= 5:
                analysis['market_health'] = 'fair'
                analysis['recommendations'].append("Proceed with caution, focus on low-risk opportunities")
            else:
                analysis['market_health'] = 'poor'
                analysis['recommendations'].append("Market conditions poor, avoid high-risk investments")
            
            # Liquidity assessment
            if high_liquidity_pools / total_pools >= 0.5:
                analysis['market_liquidity'] = 'high'
            elif high_liquidity_pools / total_pools >= 0.3:
                analysis['market_liquidity'] = 'medium'
            else:
                analysis['market_liquidity'] = 'low'
                analysis['recommendations'].append("Low market liquidity detected, be cautious with position sizes")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing market conditions: {e}")
            return {'market_health': 'unknown', 'recommendations': []}
