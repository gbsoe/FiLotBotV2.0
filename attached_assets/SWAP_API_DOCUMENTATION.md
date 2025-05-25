# Raydium Swap Transaction API Documentation

## Overview

This API provides secure, streamlined access to Raydium SDK v2 functionality for token swapping on the Solana blockchain. All endpoints use authentic Raydium protocols with advanced error handling and validation.

**Base URL:** `https://your-api-domain.com/api/raydium`

---

## Authentication

Currently, no authentication is required for quote endpoints. Execute endpoints use server-side private key management for transaction signing.

---

## Common Response Format

All endpoints return responses in this standardized format:

```json
{
  "success": boolean,
  "data": object | null,
  "error": string | null,
  "timestamp": "ISO 8601 string"
}
```

---

## Endpoints

### 1. Get Swap Quote

**Endpoint:** `GET /quote-swap`

**Description:** Retrieves a swap quote using authentic Raydium SDK v2 without executing any transaction.

#### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `inMint` | string | Yes | Input token mint address (minimum 32 characters) | `So11111111111111111111111111111111111111112` |
| `outMint` | string | Yes | Output token mint address (minimum 32 characters) | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |
| `amount` | string | Yes | Amount to swap in smallest unit (must be positive integer) | `1000000` |
| `slippagePct` | number | No | Slippage tolerance percentage (0-100, default: 0.5) | `0.5` |

#### Example Request

```bash
curl -X GET "https://your-api-domain.com/api/raydium/quote-swap?inMint=So11111111111111111111111111111111111111112&outMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=1000000&slippagePct=0.5"
```

#### Success Response (200)

```json
{
  "success": true,
  "data": {
    "inputMint": "So11111111111111111111111111111111111111112",
    "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "inputAmount": "1000000",
    "outputAmount": "95240000",
    "minimumAmountOut": "94788800",
    "priceImpact": 0.12,
    "fee": "2500",
    "route": ["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"],
    "slippage": 0.5
  },
  "timestamp": "2025-05-25T03:27:19.123Z"
}
```

#### Error Responses

**400 Bad Request - Validation Error:**
```json
{
  "success": false,
  "error": "Validation error: Invalid input mint address",
  "timestamp": "2025-05-25T03:27:19.123Z"
}
```

**500 Internal Server Error - Service Error:**
```json
{
  "success": false,
  "error": "Raydium service unavailable",
  "timestamp": "2025-05-25T03:27:19.123Z"
}
```

---

### 2. Build Swap Transaction

**Endpoint:** `POST /build-swap`

**Description:** Builds a swap transaction using Raydium SDK v2 that can be signed and executed by the client.

#### Request Body

```json
{
  "inMint": "string",
  "outMint": "string", 
  "amount": "string",
  "slippagePct": number,
  "ownerPubkey": "string"
}
```

#### Body Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `inMint` | string | Yes | Input token mint address (minimum 32 characters) | `So11111111111111111111111111111111111111112` |
| `outMint` | string | Yes | Output token mint address (minimum 32 characters) | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |
| `amount` | string | Yes | Amount to swap in smallest unit (must be positive integer) | `1000000` |
| `slippagePct` | number | No | Slippage tolerance percentage (0-100, default: 0.5) | `0.5` |
| `ownerPubkey` | string | Yes | Owner's public key who will sign the transaction | `7BgBvyjrZX1YKz4oh9mjb8ZScatkkwb8DzFx7LoiVkM3` |

#### Example Request

```bash
curl -X POST "https://your-api-domain.com/api/raydium/build-swap" \
  -H "Content-Type: application/json" \
  -d '{
    "inMint": "So11111111111111111111111111111111111111112",
    "outMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "amount": "1000000",
    "slippagePct": 0.5,
    "ownerPubkey": "7BgBvyjrZX1YKz4oh9mjb8ZScatkkwb8DzFx7LoiVkM3"
  }'
```

#### Success Response (200)

```json
{
  "success": true,
  "data": {
    "transaction": "base64-encoded-transaction-data...",
    "quote": {
      "inputMint": "So11111111111111111111111111111111111111112",
      "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
      "inputAmount": "1000000",
      "outputAmount": "95240000",
      "minimumAmountOut": "94788800",
      "priceImpact": 0.12,
      "fee": "2500",
      "route": ["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"],
      "slippage": 0.5
    },
    "signers": ["7BgBvyjrZX1YKz4oh9mjb8ZScatkkwb8DzFx7LoiVkM3"]
  },
  "timestamp": "2025-05-25T03:27:19.123Z"
}
```

#### Error Responses

**400 Bad Request - Invalid Public Key:**
```json
{
  "success": false,
  "error": "Invalid owner public key format",
  "timestamp": "2025-05-25T03:27:19.123Z"
}
```

---

### 3. Execute Swap Transaction

**Endpoint:** `POST /execute-swap`

**Description:** Executes a complete swap transaction using the server's private key. This endpoint signs and submits the transaction to the Solana network.

#### Request Body

```json
{
  "inMint": "string",
  "outMint": "string",
  "amount": "string", 
  "slippagePct": number
}
```

#### Body Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `inMint` | string | Yes | Input token mint address (minimum 32 characters) | `So11111111111111111111111111111111111111112` |
| `outMint` | string | Yes | Output token mint address (minimum 32 characters) | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |
| `amount` | string | Yes | Amount to swap in smallest unit (must be positive integer) | `1000000` |
| `slippagePct` | number | No | Slippage tolerance percentage (0-100, default: 0.5) | `0.5` |

#### Example Request

```bash
curl -X POST "https://your-api-domain.com/api/raydium/execute-swap" \
  -H "Content-Type: application/json" \
  -d '{
    "inMint": "So11111111111111111111111111111111111111112",
    "outMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "amount": "1000000",
    "slippagePct": 0.5
  }'
```

#### Success Response (200)

```json
{
  "success": true,
  "data": {
    "signature": "2Kx7p3qJ8vN9mL4wR6tY5sA1bC8dE3fG9hI0jK2lM7nO6pQ4rS5tU8vW1xY2zA3B",
    "explorerUrl": "https://solscan.io/tx/2Kx7p3qJ8vN9mL4wR6tY5sA1bC8dE3fG9hI0jK2lM7nO6pQ4rS5tU8vW1xY2zA3B",
    "quote": {
      "inputMint": "So11111111111111111111111111111111111111112",
      "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
      "inputAmount": "1000000",
      "outputAmount": "95240000",
      "minimumAmountOut": "94788800",
      "priceImpact": 0.12,
      "fee": "2500", 
      "route": ["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"],
      "slippage": 0.5
    }
  },
  "timestamp": "2025-05-25T03:27:19.123Z"
}
```

#### Error Responses

**400 Bad Request - Insufficient Funds:**
```json
{
  "success": false,
  "error": "Insufficient token balance for swap",
  "timestamp": "2025-05-25T03:27:19.123Z"
}
```

**500 Internal Server Error - Transaction Failed:**
```json
{
  "success": false,
  "error": "Transaction execution failed: Network congestion",
  "timestamp": "2025-05-25T03:27:19.123Z"
}
```

---

### 4. Transfer SPL Tokens

**Endpoint:** `POST /transfer-token`

**Description:** Transfers SPL tokens from the server's wallet to a specified recipient address.

#### Request Body

```json
{
  "mint": "string",
  "toPubkey": "string",
  "amount": "string"
}
```

#### Body Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `mint` | string | Yes | Token mint address to transfer | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |
| `toPubkey` | string | Yes | Recipient's public key address | `7BgBvyjrZX1YKz4oh9mjb8ZScatkkwb8DzFx7LoiVkM3` |
| `amount` | string | Yes | Amount to transfer in smallest unit | `1000000` |

#### Example Request

```bash
curl -X POST "https://your-api-domain.com/api/raydium/transfer-token" \
  -H "Content-Type: application/json" \
  -d '{
    "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "toPubkey": "7BgBvyjrZX1YKz4oh9mjb8ZScatkkwb8DzFx7LoiVkM3",
    "amount": "1000000"
  }'
```

#### Success Response (200)

```json
{
  "success": true,
  "data": {
    "signature": "3Ly8q4rK9wO0nM5xS7uZ6tB2cD9eF4gH0iJ1kL3mN8oP7qR5sT6uV9wX2yA4zB5C",
    "explorerUrl": "https://solscan.io/tx/3Ly8q4rK9wO0nM5xS7uZ6tB2cD9eF4gH0iJ1kL3mN8oP7qR5sT6uV9wX2yA4zB5C",
    "fromAddress": "ServerWalletAddressHere...",
    "toAddress": "7BgBvyjrZX1YKz4oh9mjb8ZScatkkwb8DzFx7LoiVkM3",
    "amount": "1000000",
    "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
  },
  "timestamp": "2025-05-25T03:27:19.123Z"
}
```

---

### 5. Health Check

**Endpoint:** `GET /health`

**Description:** Checks the status and connectivity of the Raydium service.

#### Example Request

```bash
curl -X GET "https://your-api-domain.com/api/raydium/health"
```

#### Success Response (200)

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "raydiumConnected": true,
    "networkLatency": 45
  },
  "timestamp": "2025-05-25T03:27:19.123Z"
}
```

---

## Error Handling

### Error Types

1. **Validation Errors (400):** Invalid request parameters or format
2. **Service Errors (500):** Raydium SDK or network connectivity issues  
3. **Transaction Errors (500):** Blockchain transaction execution failures

### Common Error Codes

| Status Code | Description | Possible Causes |
|-------------|-------------|-----------------|
| 400 | Bad Request | Invalid parameters, malformed addresses, negative amounts |
| 429 | Too Many Requests | Rate limiting exceeded |
| 500 | Internal Server Error | Raydium service issues, network problems |
| 503 | Service Unavailable | Temporary service downtime |

---

## Rate Limiting

- **Quote endpoints:** 100 requests per minute per IP
- **Transaction endpoints:** 10 requests per minute per IP
- **Health check:** 300 requests per minute per IP

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

---

## Data Types & Validation

### Token Addresses
- Must be valid Solana public keys (32+ characters)
- Base58 encoded strings
- Example: `So11111111111111111111111111111111111111112`

### Amounts
- String format to handle large numbers precisely
- Represent values in smallest token units (considering decimals)
- Example: For USDC (6 decimals), "1000000" = 1.0 USDC

### Slippage
- Percentage value between 0 and 100
- Default: 0.5 (0.5%)
- Higher values allow more price movement tolerance

---

## SDK Integration Examples

### JavaScript/TypeScript

```typescript
interface SwapQuoteParams {
  inMint: string;
  outMint: string;
  amount: string;
  slippagePct?: number;
}

async function getSwapQuote(params: SwapQuoteParams) {
  const queryParams = new URLSearchParams({
    inMint: params.inMint,
    outMint: params.outMint,
    amount: params.amount,
    slippagePct: params.slippagePct?.toString() || '0.5'
  });
  
  const response = await fetch(`/api/raydium/quote-swap?${queryParams}`);
  const data = await response.json();
  
  if (!data.success) {
    throw new Error(data.error);
  }
  
  return data.data;
}

async function executeSwap(params: Omit<SwapQuoteParams, 'slippagePct'> & { slippagePct?: number }) {
  const response = await fetch('/api/raydium/execute-swap', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  
  const data = await response.json();
  
  if (!data.success) {
    throw new Error(data.error);
  }
  
  return data.data;
}
```

### Python

```python
import requests
from typing import Optional, Dict, Any

class RaydiumAPI:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
    
    def get_swap_quote(self, in_mint: str, out_mint: str, amount: str, slippage_pct: Optional[float] = 0.5) -> Dict[Any, Any]:
        params = {
            'inMint': in_mint,
            'outMint': out_mint,
            'amount': amount,
            'slippagePct': slippage_pct
        }
        
        response = requests.get(f'{self.base_url}/api/raydium/quote-swap', params=params)
        data = response.json()
        
        if not data['success']:
            raise Exception(data['error'])
        
        return data['data']
    
    def execute_swap(self, in_mint: str, out_mint: str, amount: str, slippage_pct: Optional[float] = 0.5) -> Dict[Any, Any]:
        payload = {
            'inMint': in_mint,
            'outMint': out_mint,
            'amount': amount,
            'slippagePct': slippage_pct
        }
        
        response = requests.post(f'{self.base_url}/api/raydium/execute-swap', json=payload)
        data = response.json()
        
        if not data['success']:
            raise Exception(data['error'])
        
        return data['data']
```

---

## Security Considerations

1. **Private Key Management:** Server-side private keys are stored securely and never exposed in responses
2. **Input Validation:** All parameters are validated using Zod schemas before processing
3. **Rate Limiting:** Implemented to prevent abuse and ensure fair usage
4. **Error Sanitization:** Internal errors are sanitized before being returned to clients
5. **HTTPS Only:** All production endpoints must use HTTPS encryption

---

## Support & Troubleshooting

### Common Issues

**"Invalid mint address" Error:**
- Ensure token addresses are valid Solana public keys
- Check that addresses are exactly 44 characters (base58 encoded)

**"Insufficient liquidity" Error:**
- Try reducing the swap amount
- Check if the token pair has adequate liquidity on Raydium

**"Slippage tolerance exceeded" Error:**
- Increase the slippagePct parameter
- Market conditions may be volatile

**"Transaction failed" Error:**
- Check network congestion on Solana
- Verify sufficient SOL for transaction fees
- Ensure token balances are adequate

### Network Information

- **Mainnet RPC:** Uses authenticated Raydium SDK v2 connections
- **Transaction Confirmation:** Transactions are confirmed before returning success
- **Explorer Links:** All transaction signatures include Solscan explorer URLs

---

## Changelog

### v1.0.0
- Initial release with core swap functionality
- GET /quote-swap endpoint
- POST /build-swap endpoint  
- POST /execute-swap endpoint
- POST /transfer-token endpoint
- GET /health endpoint
- Comprehensive error handling and validation

---

*This documentation is automatically generated and reflects the current API implementation. For the latest updates, refer to the official repository.*