"""
Raydium Swap API client for executing transactions.
Handles swap quotes and execution using the Raydium SDK v2 API.
"""

import aiohttp
import asyncio
from typing import Dict, Any, Optional
from loguru import logger
from config import Config


class RaydiumError(Exception):
    """Custom exception for Raydium API errors."""
    pass


class RaydiumClient:
    """
    Async client for Raydium Swap API operations.
    Provides methods for getting quotes and executing swaps.
    """
    
    def __init__(self, config: Config):
        self.base_url = config.RAYDIUM_BASE_URL
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=30)
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, endpoint: str, 
                          data: Optional[Dict] = None,
                          params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make an HTTP request to the Raydium API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
            
        Returns:
            API response as dictionary
            
        Raises:
            RaydiumError: If the API request fails
        """
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.debug(f"Making {method} request to {url}")
            
            kwargs = {}
            if data:
                kwargs['json'] = data
            if params:
                kwargs['params'] = params
            
            async with self.session.request(method, url, **kwargs) as response:
                response_data = await response.json()
                
                if response.status >= 400:
                    error_msg = response_data.get('error', f'HTTP {response.status}')
                    logger.error(f"Raydium API error: {error_msg}")
                    raise RaydiumError(f"API error: {error_msg}")
                
                if not response_data.get('success', True):
                    error_msg = response_data.get('error', 'Unknown error')
                    logger.error(f"Raydium API failed: {error_msg}")
                    raise RaydiumError(f"API failed: {error_msg}")
                
                return response_data.get('data', response_data)
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {e}")
            raise RaydiumError(f"Connection error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in Raydium API request: {e}")
            raise RaydiumError(f"Request failed: {e}")
    
    async def get_swap_quote(self, in_mint: str, out_mint: str, 
                           amount: str, slippage_pct: float = 0.5) -> Dict[str, Any]:
        """
        Get a swap quote using authentic Raydium SDK v2.
        
        Args:
            in_mint: Input token mint address
            out_mint: Output token mint address
            amount: Amount to swap in smallest unit
            slippage_pct: Slippage tolerance percentage (0-100)
            
        Returns:
            Quote information including:
            - inputAmount: Input amount
            - outputAmount: Expected output amount
            - priceImpact: Price impact percentage
            - minimumAmountOut: Minimum guaranteed output
            - route: Swap route information
        """
        try:
            params = {
                'inMint': in_mint,
                'outMint': out_mint,
                'amount': str(amount),
                'slippagePct': slippage_pct
            }
            
            response = await self._make_request("GET", "/quote-swap", params=params)
            
            logger.debug(f"Got Raydium swap quote: {in_mint} -> {out_mint}")
            return response
            
        except RaydiumError:
            raise
        except Exception as e:
            logger.error(f"Failed to get Raydium swap quote: {e}")
            raise RaydiumError(f"Failed to get swap quote: {e}")
    
    async def build_swap_transaction(self, in_mint: str, out_mint: str, 
                                   amount: str, owner_pubkey: str,
                                   slippage_pct: float = 0.5) -> Dict[str, Any]:
        """
        Build a swap transaction that can be signed by the client.
        
        Args:
            in_mint: Input token mint address
            out_mint: Output token mint address
            amount: Amount to swap in smallest unit
            owner_pubkey: Owner's public key who will sign the transaction
            slippage_pct: Slippage tolerance percentage
            
        Returns:
            Transaction data including:
            - transaction: Base64-encoded transaction data
            - quote: Swap quote information
            - signers: Required signers
        """
        try:
            swap_data = {
                "inMint": in_mint,
                "outMint": out_mint,
                "amount": str(amount),
                "slippagePct": slippage_pct,
                "ownerPubkey": owner_pubkey
            }
            
            response = await self._make_request("POST", "/build-swap", data=swap_data)
            
            logger.debug(f"Built Raydium swap transaction: {in_mint} -> {out_mint}")
            return response
            
        except RaydiumError:
            raise
        except Exception as e:
            logger.error(f"Failed to build Raydium swap transaction: {e}")
            raise RaydiumError(f"Failed to build swap transaction: {e}")
    
    async def execute_swap(self, in_mint: str, out_mint: str, 
                          amount: str, slippage_pct: float = 0.5) -> Dict[str, Any]:
        """
        Execute a complete swap transaction using server's private key.
        
        Args:
            in_mint: Input token mint address
            out_mint: Output token mint address
            amount: Amount to swap in smallest unit
            slippage_pct: Slippage tolerance percentage
            
        Returns:
            Execution result including:
            - signature: Transaction signature
            - explorerUrl: Solscan explorer URL
            - quote: Swap quote information
        """
        try:
            swap_data = {
                "inMint": in_mint,
                "outMint": out_mint,
                "amount": str(amount),
                "slippagePct": slippage_pct
            }
            
            response = await self._make_request("POST", "/execute-swap", data=swap_data)
            
            logger.info(f"Executed Raydium swap: {in_mint} -> {out_mint}, signature: {response.get('signature')}")
            return response
            
        except RaydiumError:
            raise
        except Exception as e:
            logger.error(f"Failed to execute Raydium swap: {e}")
            raise RaydiumError(f"Failed to execute swap: {e}")
    
    async def transfer_token(self, mint: str, to_pubkey: str, amount: str) -> Dict[str, Any]:
        """
        Transfer SPL tokens from the server's wallet to a recipient.
        
        Args:
            mint: Token mint address to transfer
            to_pubkey: Recipient's public key address
            amount: Amount to transfer in smallest unit
            
        Returns:
            Transfer result including:
            - signature: Transaction signature
            - explorerUrl: Solscan explorer URL
            - fromAddress: Sender address
            - toAddress: Recipient address
        """
        try:
            transfer_data = {
                "mint": mint,
                "toPubkey": to_pubkey,
                "amount": str(amount)
            }
            
            response = await self._make_request("POST", "/transfer-token", data=transfer_data)
            
            logger.info(f"Transferred token: {mint} to {to_pubkey}, signature: {response.get('signature')}")
            return response
            
        except RaydiumError:
            raise
        except Exception as e:
            logger.error(f"Failed to transfer token: {e}")
            raise RaydiumError(f"Failed to transfer token: {e}")
    
    async def health_check(self) -> bool:
        """
        Check if the Raydium API is healthy.
        
        Returns:
            True if the API is responding, False otherwise
        """
        try:
            response = await self._make_request("GET", "/health")
            
            is_healthy = (
                response.get('status') == 'healthy' or
                response.get('raydiumConnected') == True or
                'healthy' in str(response).lower()
            )
            
            if is_healthy:
                logger.info("Raydium API health check passed")
            else:
                logger.warning(f"Raydium API health check unclear: {response}")
            
            return is_healthy
            
        except Exception as e:
            logger.error(f"Raydium API health check failed: {e}")
            return False