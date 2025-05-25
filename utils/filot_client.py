"""
FiLot API client for interacting with the FiLot microservice.
Handles all external API calls for pool data and trading operations.
"""

import aiohttp
import asyncio
from typing import Dict, List, Optional, Any
from loguru import logger
from config import Config

class FiLotError(Exception):
    """Custom exception for FiLot API errors."""
    pass

class FiLotClient:
    """
    Async client for FiLot API operations.
    Provides methods for fetching pool data, getting quotes, and executing trades.
    """
    
    def __init__(self, config: Config):
        self.base_url = config.FILOT_BASE_URL
        self.private_key = config.SOLANA_PRIVATE_KEY
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, endpoint: str, 
                          data: Optional[Dict] = None,
                          params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make an HTTP request to the FiLot API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
            
        Returns:
            API response as dictionary
            
        Raises:
            FiLotError: If the API request fails
        """
        if not self.session:
            raise FiLotError("Client session not initialized")
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                response_data = await response.json()
                
                if response.status >= 400:
                    error_msg = response_data.get('error', f'HTTP {response.status}')
                    logger.error(f"FiLot API error: {error_msg}")
                    raise FiLotError(f"API request failed: {error_msg}")
                
                return response_data
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {e}")
            raise FiLotError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in API request: {e}")
            raise FiLotError(f"Request failed: {e}")
    
    async def get_pools(self) -> List[Dict[str, Any]]:
        """
        Fetch all available Raydium pools.
        
        Returns:
            List of pool data dictionaries containing:
            - poolId: Unique pool identifier
            - tokenA: First token in the pair
            - tokenB: Second token in the pair
            - tvl: Total Value Locked
            - volume24h: 24-hour trading volume
            - apy: Annual Percentage Yield
            - feeRate: Pool fee rate
        """
        try:
            response = await self._make_request("GET", "/api/pools")
            pools = response.get('pools', [])
            
            logger.info(f"Fetched {len(pools)} pools from FiLot API")
            return pools
            
        except FiLotError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch pools: {e}")
            raise FiLotError(f"Failed to fetch pools: {e}")
    
    async def get_pool_details(self, pool_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific pool.
        
        Args:
            pool_id: The pool identifier
            
        Returns:
            Detailed pool information
        """
        try:
            response = await self._make_request(
                "GET", 
                f"/api/pools/{pool_id}"
            )
            
            logger.debug(f"Fetched details for pool {pool_id}")
            return response
            
        except FiLotError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch pool details for {pool_id}: {e}")
            raise FiLotError(f"Failed to fetch pool details: {e}")
    
    async def get_swap_quote(self, input_token: str, output_token: str, 
                           amount: float, slippage: float = 1.0) -> Dict[str, Any]:
        """
        Get a quote for a token swap.
        
        Args:
            input_token: Token to swap from
            output_token: Token to swap to
            amount: Amount to swap
            slippage: Maximum slippage percentage (default 1%)
            
        Returns:
            Quote information including:
            - expectedOutput: Expected output amount
            - priceImpact: Price impact percentage
            - minimumOutput: Minimum guaranteed output
            - route: Swap route information
        """
        try:
            quote_data = {
                "inputToken": input_token,
                "outputToken": output_token,
                "amount": amount,
                "slippage": slippage
            }
            
            response = await self._make_request(
                "POST", 
                "/api/swap/quote", 
                data=quote_data
            )
            
            logger.debug(f"Got swap quote: {input_token} -> {output_token}, amount: {amount}")
            return response
            
        except FiLotError:
            raise
        except Exception as e:
            logger.error(f"Failed to get swap quote: {e}")
            raise FiLotError(f"Failed to get swap quote: {e}")
    
    async def execute_swap(self, input_token: str, output_token: str, 
                          amount: float, slippage: float = 1.0,
                          simulate: bool = False) -> Dict[str, Any]:
        """
        Execute a token swap.
        
        Args:
            input_token: Token to swap from
            output_token: Token to swap to
            amount: Amount to swap
            slippage: Maximum slippage percentage
            simulate: If True, only simulate the transaction
            
        Returns:
            Execution result including:
            - transactionHash: Transaction hash (if not simulated)
            - actualOutput: Actual output amount
            - gasUsed: Gas consumed
            - success: Whether the swap succeeded
        """
        try:
            swap_data = {
                "inputToken": input_token,
                "outputToken": output_token,
                "amount": amount,
                "slippage": slippage,
                "privateKey": self.private_key,
                "simulate": simulate
            }
            
            response = await self._make_request(
                "POST", 
                "/api/swap/execute", 
                data=swap_data
            )
            
            if simulate:
                logger.info(f"Simulated swap: {input_token} -> {output_token}")
            else:
                logger.info(f"Executed swap: {input_token} -> {output_token}, tx: {response.get('transactionHash')}")
            
            return response
            
        except FiLotError:
            raise
        except Exception as e:
            logger.error(f"Failed to execute swap: {e}")
            raise FiLotError(f"Failed to execute swap: {e}")
    
    async def get_pool_metrics(self, pool_id: str, timeframe: str = "24h") -> Dict[str, Any]:
        """
        Get detailed metrics for a pool.
        
        Args:
            pool_id: The pool identifier
            timeframe: Time period for metrics (1h, 24h, 7d, 30d)
            
        Returns:
            Pool metrics including volume, fees, liquidity changes
        """
        try:
            params = {"timeframe": timeframe}
            response = await self._make_request(
                "GET", 
                f"/api/pools/{pool_id}/metrics",
                params=params
            )
            
            logger.debug(f"Fetched metrics for pool {pool_id}")
            return response
            
        except FiLotError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch pool metrics for {pool_id}: {e}")
            raise FiLotError(f"Failed to fetch pool metrics: {e}")
    
    async def get_wallet_balance(self, wallet_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Get wallet token balances.
        
        Args:
            wallet_address: Wallet address (if None, uses the bot's wallet)
            
        Returns:
            Dictionary of token balances
        """
        try:
            params = {}
            if wallet_address:
                params["address"] = wallet_address
            else:
                # Use the wallet derived from private key
                params["privateKey"] = self.private_key
            
            response = await self._make_request(
                "GET", 
                "/api/wallet/balance",
                params=params
            )
            
            logger.debug("Fetched wallet balance")
            return response
            
        except FiLotError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch wallet balance: {e}")
            raise FiLotError(f"Failed to fetch wallet balance: {e}")
    
    async def health_check(self) -> bool:
        """
        Check if the FiLot API is healthy.
        
        Returns:
            True if the API is responding, False otherwise
        """
        try:
            await self._make_request("GET", "/api/health")
            return True
        except:
            return False
