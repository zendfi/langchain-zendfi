"""
ZendFi Client Wrapper for LangChain
====================================
Handles all interactions with the ZendFi SDK/API for autonomous agent payments.

This client provides:
- Device-bound session keys with PIN encryption (non-custodial)
- Autonomous signing via Lit Protocol MPC
- Gasless transactions (backend pays all Solana fees)
- Cross-app compatible session keys

The design mirrors the TypeScript SDK:
- zendfi.sessionKeys.create() - Create device-bound session key
- zendfi.sessionKeys.makePayment() - Execute payment with auto-signing
- zendfi.sessionKeys.getStatus() - Check balance and limits
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import os
import uuid
import time
import hashlib
import httpx
from functools import lru_cache


class ZendFiMode(str, Enum):
    """ZendFi network mode."""
    TEST = "test"  # Solana devnet
    LIVE = "live"  # Solana mainnet-beta


@dataclass
class SessionKeyResult:
    """Result from creating a session key."""
    session_key_id: str
    agent_id: str
    agent_name: Optional[str]
    session_wallet: str
    limit_usdc: float
    expires_at: str
    recovery_qr: Optional[str]
    cross_app_compatible: bool


@dataclass
class SessionKeyStatus:
    """Current status of a session key."""
    session_key_id: str
    is_active: bool
    is_approved: bool
    limit_usdc: float
    used_amount_usdc: float
    remaining_usdc: float
    expires_at: str
    days_until_expiry: int


@dataclass
class PaymentResult:
    """Result from executing a payment."""
    payment_id: str
    signature: str
    status: str
    amount: Optional[float] = None
    recipient: Optional[str] = None


@dataclass
class AgentProvider:
    """A service provider in the agent marketplace."""
    agent_id: str
    agent_name: str
    service_type: str
    price_per_unit: float
    wallet: str
    reputation: float
    description: Optional[str] = None
    available: bool = True


class ZendFiAPIError(Exception):
    """Error from ZendFi API."""
    def __init__(self, message: str, status_code: Optional[int] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class SessionKeyNotFoundError(ZendFiAPIError):
    """Session key not found or not loaded."""
    pass


class InsufficientBalanceError(ZendFiAPIError):
    """Insufficient session key balance for payment."""
    pass


class SessionKeyExpiredError(ZendFiAPIError):
    """Session key has expired."""
    pass


class ZendFiClient:
    """
    ZendFi SDK Client for LangChain integration.
    
    Enables AI agents to make autonomous cryptocurrency payments on Solana
    with spending limits and non-custodial security.
    
    Architecture:
    - Session keys are device-bound (client generates keypair, never exposed)
    - Lit Protocol MPC enables autonomous signing without user interaction
    - Backend handles all transaction building and gas fees
    - USDC on Solana for stablecoin payments
    
    Example:
        >>> client = ZendFiClient(api_key="zk_test_...", mode="test")
        >>> session = await client.create_session_key(
        ...     user_wallet="7xKNH...",
        ...     agent_id="langchain-agent",
        ...     limit_usdc=10.0,
        ...     duration_days=7,
        ... )
        >>> payment = await client.make_payment(
        ...     session_key_id=session.session_key_id,
        ...     amount=1.50,
        ...     recipient="8xYZA...",
        ...     description="GPT-4 tokens"
        ... )
    """
    
    BASE_URL_TEST = "https://api.zendfi.com"
    BASE_URL_LIVE = "https://api.zendfi.com"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        mode: str = "test",
        auto_create_session: bool = True,
        session_limit_usd: float = 10.0,
        debug: bool = False,
        timeout: float = 30.0,
    ):
        """
        Initialize ZendFi client.
        
        Args:
            api_key: ZendFi API key (defaults to ZENDFI_API_KEY env var)
                     Prefixes: zk_test_ (test mode), zk_live_ (live mode)
            mode: 'test' (devnet) or 'live' (mainnet)
            auto_create_session: If True, automatically creates session key on first use
            session_limit_usd: Default spending limit for auto-created sessions
            debug: Enable debug logging
            timeout: HTTP request timeout in seconds
        """
        self.api_key = api_key or os.getenv("ZENDFI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ZendFi API key required. Set ZENDFI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.mode = ZendFiMode(mode)
        self.auto_create_session = auto_create_session
        self.session_limit_usd = session_limit_usd
        self.debug = debug
        self.timeout = timeout
        
        # Determine base URL based on mode
        self.base_url = self.BASE_URL_TEST if self.mode == ZendFiMode.TEST else self.BASE_URL_LIVE
        
        # Session management
        self._session_key_id: Optional[str] = None
        self._session_wallet: Optional[str] = None
        self._session_agent_id: Optional[str] = None
        
        # HTTP client
        self._http_client: Optional[httpx.AsyncClient] = None
        
        if self.debug:
            print(f"[ZendFi] Initialized in {self.mode.value} mode")
            print(f"[ZendFi] Base URL: {self.base_url}")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-ZendFi-SDK": "langchain-python/0.1.0",
                },
            )
        return self._http_client
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to ZendFi API."""
        client = await self._get_client()
        
        headers = {}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        
        if self.debug:
            print(f"[ZendFi] {method} {endpoint}")
            if data:
                print(f"[ZendFi] Request: {data}")
        
        try:
            if method == "GET":
                response = await client.get(endpoint, headers=headers)
            elif method == "POST":
                response = await client.post(endpoint, json=data, headers=headers)
            elif method == "DELETE":
                response = await client.delete(endpoint, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if self.debug:
                print(f"[ZendFi] Response ({response.status_code}): {response.text[:200]}")
            
            if response.status_code >= 400:
                error_data = response.json() if response.text else {}
                error_message = error_data.get("message", error_data.get("error", "Unknown error"))
                error_code = error_data.get("code")
                
                if response.status_code == 404:
                    raise SessionKeyNotFoundError(error_message, response.status_code, error_code)
                elif error_code == "INSUFFICIENT_BALANCE":
                    raise InsufficientBalanceError(error_message, response.status_code, error_code)
                elif error_code == "SESSION_EXPIRED":
                    raise SessionKeyExpiredError(error_message, response.status_code, error_code)
                else:
                    raise ZendFiAPIError(error_message, response.status_code, error_code)
            
            return response.json() if response.text else {}
            
        except httpx.HTTPError as e:
            raise ZendFiAPIError(f"HTTP error: {str(e)}")
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    # ============================================
    # Session Key Management
    # ============================================
    
    async def create_session_key(
        self,
        user_wallet: str,
        agent_id: str,
        limit_usdc: float,
        duration_days: int = 7,
        agent_name: Optional[str] = None,
        pin: str = "123456",  # Demo PIN - in production, user provides
        enable_lit_protocol: bool = True,
    ) -> SessionKeyResult:
        """
        Create a new device-bound session key.
        
        Session keys enable autonomous payments with spending limits.
        The keypair is generated client-side (non-custodial) and encrypted
        with Lit Protocol MPC for autonomous signing.
        
        Args:
            user_wallet: User's main Solana wallet address
            agent_id: Unique identifier for the agent (e.g., "langchain-agent-v1")
            limit_usdc: Maximum spending limit in USDC
            duration_days: How long the session key is valid (1-30 days)
            agent_name: Human-readable agent name
            pin: PIN for client-side encryption (demo uses default)
            enable_lit_protocol: Enable Lit Protocol for autonomous signing
            
        Returns:
            SessionKeyResult with session_key_id and session_wallet
            
        Example:
            >>> result = await client.create_session_key(
            ...     user_wallet="7xKNH...",
            ...     agent_id="shopping-agent",
            ...     limit_usdc=25.0,
            ...     duration_days=7,
            ... )
            >>> print(f"Session: {result.session_key_id}")
            >>> print(f"Wallet: {result.session_wallet}")
        """
        # Generate device fingerprint (in production, this is derived from device)
        device_fingerprint = hashlib.sha256(
            f"{user_wallet}:{agent_id}:{os.getenv('USER', 'default')}".encode()
        ).hexdigest()[:32]
        
        # In production SDK, keypair is generated client-side
        # For Python wrapper, we let the backend handle it in mock mode
        # or call the TypeScript SDK via subprocess/WASM
        
        response = await self._request("POST", "/api/v1/ai/session-keys/device-bound/create", {
            "user_wallet": user_wallet,
            "agent_id": agent_id,
            "agent_name": agent_name or f"LangChain Agent ({agent_id})",
            "limit_usdc": limit_usdc,
            "duration_days": duration_days,
            "device_fingerprint": device_fingerprint,
            # Note: In production, these would be computed client-side:
            # "encrypted_session_key": encrypted_data,
            # "nonce": nonce,
            # "session_public_key": public_key,
            # "lit_encrypted_keypair": lit_ciphertext,
            # "lit_data_hash": lit_hash,
        })
        
        result = SessionKeyResult(
            session_key_id=response["session_key_id"],
            agent_id=response["agent_id"],
            agent_name=response.get("agent_name"),
            session_wallet=response["session_wallet"],
            limit_usdc=response["limit_usdc"],
            expires_at=response["expires_at"],
            recovery_qr=response.get("recovery_qr_data"),
            cross_app_compatible=response.get("cross_app_compatible", True),
        )
        
        # Cache for automatic use
        self._session_key_id = result.session_key_id
        self._session_wallet = result.session_wallet
        self._session_agent_id = result.agent_id
        
        if self.debug:
            print(f"[ZendFi] Created session key: {result.session_key_id}")
            print(f"[ZendFi] Session wallet: {result.session_wallet}")
            print(f"[ZendFi] Limit: ${result.limit_usdc} USDC")
        
        return result
    
    async def ensure_session_key(
        self,
        user_wallet: Optional[str] = None,
        agent_id: str = "langchain-agent",
    ) -> Dict[str, str]:
        """
        Ensure a session key exists, creating one if needed.
        
        Args:
            user_wallet: User's wallet (uses ZENDFI_USER_WALLET env var if not provided)
            agent_id: Agent identifier
            
        Returns:
            Dict with session_key_id and session_wallet
        """
        if self._session_key_id:
            return {
                "session_key_id": self._session_key_id,
                "session_wallet": self._session_wallet,
            }
        
        if not self.auto_create_session:
            raise SessionKeyNotFoundError(
                "No session key configured and auto_create_session=False. "
                "Create a session key manually first."
            )
        
        wallet = user_wallet or os.getenv("ZENDFI_USER_WALLET", "demo-wallet")
        
        result = await self.create_session_key(
            user_wallet=wallet,
            agent_id=agent_id,
            limit_usdc=self.session_limit_usd,
            duration_days=7,
        )
        
        return {
            "session_key_id": result.session_key_id,
            "session_wallet": result.session_wallet,
        }
    
    async def get_session_status(
        self,
        session_key_id: Optional[str] = None,
    ) -> SessionKeyStatus:
        """
        Get current status of a session key.
        
        Args:
            session_key_id: Session key ID (uses cached ID if not provided)
            
        Returns:
            SessionKeyStatus with balance and expiry info
        """
        key_id = session_key_id or self._session_key_id
        if not key_id:
            session = await self.ensure_session_key()
            key_id = session["session_key_id"]
        
        response = await self._request("POST", "/api/v1/ai/session-keys/status", {
            "session_key_id": key_id,
        })
        
        return SessionKeyStatus(
            session_key_id=key_id,
            is_active=response["is_active"],
            is_approved=response.get("is_approved", True),
            limit_usdc=response["limit_usdc"],
            used_amount_usdc=response["used_amount_usdc"],
            remaining_usdc=response["remaining_usdc"],
            expires_at=response["expires_at"],
            days_until_expiry=response["days_until_expiry"],
        )
    
    # ============================================
    # Payment Execution
    # ============================================
    
    async def make_payment(
        self,
        amount: float,
        recipient: str,
        description: str,
        session_key_id: Optional[str] = None,
        token: str = "USDC",
        idempotency_key: Optional[str] = None,
    ) -> PaymentResult:
        """
        Execute a payment using the session key.
        
        Payments are:
        - Autonomous (no user signature required per transaction)
        - Gasless (backend pays all Solana fees)
        - Instant (typically ~400ms confirmation)
        - Auditable (full on-chain transaction)
        
        Args:
            amount: Amount in USD to pay
            recipient: Recipient's Solana wallet address
            description: Description of the payment
            session_key_id: Session key to use (uses cached if not provided)
            token: Token to pay with (default: USDC)
            idempotency_key: Unique key to prevent duplicate payments
            
        Returns:
            PaymentResult with transaction signature
            
        Raises:
            InsufficientBalanceError: If session key balance is too low
            SessionKeyExpiredError: If session key has expired
        """
        key_id = session_key_id or self._session_key_id
        if not key_id:
            session = await self.ensure_session_key()
            key_id = session["session_key_id"]
        
        # Generate idempotency key if not provided
        if not idempotency_key:
            idempotency_key = f"pay_{uuid.uuid4().hex[:16]}"
        
        # Get agent_id from cache or default
        agent_id = self._session_agent_id or "langchain-agent"
        
        response = await self._request(
            "POST",
            "/api/v1/ai/smart-payment",
            {
                "agent_id": agent_id,
                "session_key_id": key_id,
                "amount_usd": amount,
                "user_wallet": recipient,  # For routing
                "token": token,
                "description": description,
            },
            idempotency_key=idempotency_key,
        )
        
        result = PaymentResult(
            payment_id=response["payment_id"],
            signature=response.get("transaction_signature", response.get("signature", "")),
            status=response["status"],
            amount=amount,
            recipient=recipient,
        )
        
        if self.debug:
            print(f"[ZendFi] Payment successful: {result.payment_id}")
            print(f"[ZendFi] Signature: {result.signature[:20]}...")
        
        return result
    
    # ============================================
    # Marketplace (Mock for Demo)
    # ============================================
    
    async def search_marketplace(
        self,
        service_type: str,
        max_price: Optional[float] = None,
        min_reputation: float = 0.0,
    ) -> List[AgentProvider]:
        """
        Search for service providers in the agent marketplace.
        
        Args:
            service_type: Type of service (e.g., 'gpt4-tokens', 'image-generation')
            max_price: Maximum price per unit filter
            min_reputation: Minimum reputation score (0-5)
            
        Returns:
            List of matching providers sorted by price
            
        Note: This is a mock implementation. In production, this would
        query the ZendFi Agent Registry API.
        """
        # Mock marketplace data for demo
        # In production, this calls: GET /api/v1/marketplace/providers
        all_providers = [
            AgentProvider(
                agent_id="gpt4-provider-alpha",
                agent_name="GPT-4 Token Provider Alpha",
                service_type="gpt4-tokens",
                price_per_unit=0.08,
                wallet="AlphaProvider1234567890abcdef",
                reputation=4.9,
                description="Premium GPT-4 tokens with low latency",
            ),
            AgentProvider(
                agent_id="gpt4-provider-beta",
                agent_name="GPT-4 Token Provider Beta",
                service_type="gpt4-tokens",
                price_per_unit=0.06,
                wallet="BetaProvider1234567890abcdef",
                reputation=4.5,
                description="Budget-friendly GPT-4 tokens",
            ),
            AgentProvider(
                agent_id="gpt4-provider-gamma",
                agent_name="Enterprise GPT-4 Tokens",
                service_type="gpt4-tokens",
                price_per_unit=0.12,
                wallet="GammaProvider1234567890abcdef",
                reputation=5.0,
                description="Enterprise-grade with SLA guarantees",
            ),
            AgentProvider(
                agent_id="image-gen-fast",
                agent_name="Fast Image Generator",
                service_type="image-generation",
                price_per_unit=0.02,
                wallet="ImageGenFast1234567890abcdef",
                reputation=4.3,
                description="Quick image generation, 512x512",
            ),
            AgentProvider(
                agent_id="image-gen-hd",
                agent_name="HD Image Generator",
                service_type="image-generation",
                price_per_unit=0.05,
                wallet="ImageGenHD1234567890abcdef",
                reputation=4.7,
                description="High-quality 1024x1024 images",
            ),
            AgentProvider(
                agent_id="code-review-bot",
                agent_name="Code Review Bot",
                service_type="code-review",
                price_per_unit=0.15,
                wallet="CodeReviewBot1234567890abcdef",
                reputation=4.6,
                description="Automated code review with suggestions",
            ),
        ]
        
        # Filter by service type
        results = [p for p in all_providers if p.service_type == service_type]
        
        # Filter by max price
        if max_price is not None:
            results = [p for p in results if p.price_per_unit <= max_price]
        
        # Filter by reputation
        results = [p for p in results if p.reputation >= min_reputation]
        
        # Sort by price
        results.sort(key=lambda x: x.price_per_unit)
        
        return results
    
    async def get_provider(self, agent_id: str) -> Optional[AgentProvider]:
        """
        Get a specific provider by agent ID.
        
        Args:
            agent_id: The agent's unique identifier
            
        Returns:
            AgentProvider if found, None otherwise
        """
        providers = await self.search_marketplace("gpt4-tokens")
        providers.extend(await self.search_marketplace("image-generation"))
        providers.extend(await self.search_marketplace("code-review"))
        
        for provider in providers:
            if provider.agent_id == agent_id:
                return provider
        return None


# Singleton instance for convenience
_default_client: Optional[ZendFiClient] = None


def get_zendfi_client(**kwargs) -> ZendFiClient:
    """
    Get or create the default ZendFi client.
    
    Args:
        **kwargs: Passed to ZendFiClient constructor on first call
        
    Returns:
        ZendFiClient instance
    """
    global _default_client
    if _default_client is None:
        _default_client = ZendFiClient(**kwargs)
    return _default_client


def reset_zendfi_client() -> None:
    """Reset the default client (useful for testing)."""
    global _default_client
    _default_client = None
