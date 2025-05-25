"""
FiLot API client for interacting with the FiLot microservice.
Handles all external API calls for pool data and trading operations.
"""

import aiohttp
import asyncio
from typing import Dict, List, Optional, Any
from functools import wraps
from loguru import logger
from config import Config


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator to add retry logic to async functions.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay}s...")
                        await asyncio.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}")
            raise last_exception if last_exception else Exception("Unknown error occurred")
        return wrapper
    return decorator

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
    
    @retry_on_failure(max_retries=3, delay=1.0)
    async def list_pools(self) -> List[Dict[str, Any]]:
        """
        Fetch all available Raydium pools from FiLot API.
        
        Returns:
            List of pool data dictionaries containing:
            - poolId: Unique pool identifier
            - baseTokenMint: Base token mint address
            - quoteTokenMint: Quote token mint address
            - tvl: Total Value Locked
            - volume24h: 24-hour trading volume
            - apy: Annual Percentage Yield
            - baseTokenReserve: Base token reserve amount
            - quoteTokenReserve: Quote token reserve amount
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
    
    @retry_on_failure(max_retries=3, delay=1.0)
    async def get_pool(self, pool_id: str) -> Dict[str, Any]:
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
    
    @retry_on_failure(max_retries=3, delay=1.0)
    async def post_swap_quote(self, input_mint: str, output_mint: str, 
                           amount: str, slippage: float = 0.5) -> Dict[str, Any]:
        """
        Get a quote for a token swap using FiLot API.
        
        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount to swap in smallest unit (string)
            slippage: Maximum slippage percentage (default 0.5%)
            
        Returns:
            Quote information including:
            - inputAmount: Input amount
            - outputAmount: Expected output amount
            - priceImpact: Price impact percentage
            - minOutputAmount: Minimum guaranteed output
            - route: Swap route information
        """
        try:
            quote_data = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippage": slippage
            }
            
            response = await self._make_request(
                "POST", 
                "/api/swap/quote", 
                data=quote_data
            )
            
            logger.debug(f"Got swap quote: {input_mint} -> {output_mint}, amount: {amount}")
            return response
            
        except FiLotError:
            raise
        except Exception as e:
            logger.error(f"Failed to get swap quote: {e}")
            raise FiLotError(f"Failed to get swap quote: {e}")
    
    async def execute_swap(self, input_mint: str, output_mint: str, 
                          amount: str, slippage: float = 0.5) -> Dict[str, Any]:
        """
        Execute a token swap using Raydium API (Note: This is for future implementation).
        Currently returns quote data as FiLot API doesn't provide execution endpoint.
        
        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount to swap in smallest unit
            slippage: Maximum slippage percentage
            
        Returns:
            Execution simulation result
        """
        try:
            # For now, return quote data since FiLot API doesn't have execute endpoint
            # This would need to be integrated with actual Raydium SDK for execution
            quote_data = await self.get_swap_quote(input_mint, output_mint, amount, slippage)
            
            # Simulate execution response
            simulated_response = {
                "success": True,
                "signature": "simulated_transaction_signature",
                "explorerUrl": f"https://solscan.io/tx/simulated_transaction_signature",
                "quote": quote_data
            }
            
            logger.info(f"Simulated swap execution: {input_mint} -> {output_mint}")
            return simulated_response
            
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


if __name__ == "__main__":
    """
    Smoke test for FiLot client - prints first three pool IDs.
    """
    import os
    from config import Config
    
    async def smoke_test():
        config = Config()
        
        async with FiLotClient(config) as client:
            try:
                pools = await client.list_pools()
                print(f"Successfully fetched {len(pools)} pools from FiLot API")
                
                if pools:
                    print("First three pool IDs:")
                    for i, pool in enumerate(pools[:3]):
                        pool_id = pool.get('poolId', 'Unknown')
                        print(f"{i+1}. {pool_id}")
                else:
                    print("No pools found")
                    
            except Exception as e:
                print(f"Smoke test failed: {e}")
    
    asyncio.run(smoke_test())
