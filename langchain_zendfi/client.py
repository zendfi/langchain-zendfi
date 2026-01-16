"""
ZendFi Client - Production API Integration
===========================================
Direct HTTP client for ZendFi's Agentic Intent Protocol (AIP) APIs.

Makes real HTTP calls to ZendFi's REST API, matching the TypeScript SDK's
exact endpoint structure. Designed for production use with LangChain agents.

API Endpoints (from TypeScript SDK analysis):
- POST /api/v1/ai/sessions - Create agent session with spending limits
- GET /api/v1/ai/sessions/{id} - Get session details
- POST /api/v1/ai/smart-payment - Execute AI-powered payment
- POST /api/v1/ai/payments/{id}/submit-signed - Submit signed transaction
- POST /api/v1/ai/session-keys/device-bound/create - Create device-bound key
- POST /api/v1/ai/session-keys/status - Get session key status
- POST /api/v1/ai/pricing/ppp-factor - Get PPP factor
- POST /api/v1/ai/pricing/suggest - Get AI pricing suggestion

Key Features:
- Agent Sessions: Spending limits without client-side crypto
- Smart Payments: AI-powered routing with gasless option
- Session Keys: Device-bound non-custodial with Lit Protocol MPC
- PPP Pricing: Location-based price adjustments
"""

from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
from enum import Enum
import os
import uuid
import time
import hashlib
import asyncio
import httpx

# SDK Version for User-Agent
SDK_VERSION = "0.1.0"


class ZendFiMode(str, Enum):
    """ZendFi network mode."""
    TEST = "test"  # Solana devnet
    LIVE = "live"  # Solana mainnet-beta


# ============================================
# Data Classes (matching TypeScript SDK types)
# ============================================

@dataclass
class SessionLimits:
    """Spending limits for agent sessions."""
    max_per_transaction: float = 1000.0
    max_per_day: float = 5000.0
    max_per_week: float = 20000.0
    max_per_month: float = 50000.0
    require_approval_above: float = 500.0


@dataclass
class AgentSession:
    """Agent session with spending limits."""
    id: str
    session_token: str
    agent_id: str
    user_wallet: str
    limits: SessionLimits
    is_active: bool
    created_at: str
    expires_at: str
    remaining_today: float
    remaining_this_week: float
    remaining_this_month: float
    agent_name: Optional[str] = None
    pkp_address: Optional[str] = None


@dataclass
class SessionKeyResult:
    """Result from creating a device-bound session key."""
    session_key_id: str
    agent_id: str
    session_wallet: str
    limit_usdc: float
    expires_at: str
    cross_app_compatible: bool
    agent_name: Optional[str] = None
    requires_client_signing: bool = True
    mode: str = "device_bound"


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
    """Result from executing a payment (legacy structure)."""
    payment_id: str
    signature: str
    status: str
    amount: Optional[float] = None
    recipient: Optional[str] = None


@dataclass
class SmartPaymentResult:
    """Result from executing a smart payment."""
    payment_id: str
    status: str  # 'pending', 'confirmed', 'awaiting_signature', 'failed'
    amount_usd: float
    gasless_used: bool
    settlement_complete: bool
    receipt_url: str
    next_steps: str
    created_at: str
    transaction_signature: Optional[str] = None
    unsigned_transaction: Optional[str] = None
    requires_signature: bool = False
    submit_url: Optional[str] = None
    escrow_id: Optional[str] = None
    confirmed_in_ms: Optional[int] = None


@dataclass
class PPPFactor:
    """Purchasing Power Parity factor for a country."""
    country_code: str
    country_name: str
    ppp_factor: float
    currency_code: str
    adjustment_percentage: float


@dataclass
class PricingSuggestion:
    """AI-powered pricing suggestion."""
    suggested_amount: float
    min_amount: float
    max_amount: float
    currency: str
    reasoning: str
    ppp_adjusted: bool
    adjustment_factor: Optional[float] = None


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


# ============================================
# Exceptions
# ============================================

class ZendFiAPIError(Exception):
    """Base error from ZendFi API."""
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.details = details


class AuthenticationError(ZendFiAPIError):
    """API key is invalid or missing."""
    pass


class SessionKeyNotFoundError(ZendFiAPIError):
    """Session key not found."""
    pass


class InsufficientBalanceError(ZendFiAPIError):
    """Insufficient session key balance for payment."""
    pass


class SessionKeyExpiredError(ZendFiAPIError):
    """Session key has expired."""
    pass


class RateLimitError(ZendFiAPIError):
    """Rate limit exceeded."""
    pass


class ValidationError(ZendFiAPIError):
    """Request validation failed."""
    pass


class ZendFiClient:
    """
    Production ZendFi API Client for LangChain Integration.
    
    Makes real HTTP calls to ZendFi's REST API following the exact
    endpoint structure from the TypeScript SDK's Agentic Intent Protocol.
    
    Two Session Models:
    1. Agent Sessions (Recommended): Server-managed spending limits
       - No client-side cryptography required
       - Perfect for LangChain and server-side agents
       
    2. Device-Bound Session Keys: Client-side cryptography
       - Requires keypair generation and encryption
       - Best for browser/mobile apps
    
    Example:
        >>> client = ZendFiClient(api_key="zk_test_...", mode="test")
        >>> 
        >>> # Create agent session with spending limits
        >>> session = await client.create_agent_session(
        ...     agent_id="langchain-agent",
        ...     user_wallet="7xKNH...",
        ...     limits=SessionLimits(max_per_day=100.0),
        ... )
        >>> 
        >>> # Make smart payment
        >>> payment = await client.smart_payment(
        ...     agent_id="langchain-agent",
        ...     user_wallet="7xKNH...",
        ...     amount_usd=1.50,
        ...     description="GPT-4 tokens",
        ...     session_token=session.session_token,
        ... )
    """
    
    # API Base URL (same for test/live, differentiated by API key)
    BASE_URL = "https://api.zendfi.com"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        mode: str = "test",
        auto_create_session: bool = True,
        session_limit_usd: float = 10.0,
        debug: bool = False,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize ZendFi client.
        
        Args:
            api_key: ZendFi API key (defaults to ZENDFI_API_KEY env var)
                     Prefixes: zk_test_ (devnet), zk_live_ (mainnet)
            mode: 'test' (devnet) or 'live' (mainnet)
            auto_create_session: If True, auto-creates session on first payment
            session_limit_usd: Default spending limit for auto-created sessions
            debug: Enable debug logging
            timeout: HTTP request timeout in seconds
            max_retries: Maximum retry attempts for transient failures
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
        self.max_retries = max_retries
        
        self.base_url = self.BASE_URL
        
        # Session caching
        self._cached_session: Optional[AgentSession] = None
        self._session_key_id: Optional[str] = None
        self._session_wallet: Optional[str] = None
        self._session_agent_id: Optional[str] = None
        
        # HTTP client (lazy initialized)
        self._http_client: Optional[httpx.AsyncClient] = None
        
        if self.debug:
            print(f"[ZendFi] Initialized in {self.mode.value} mode")
            print(f"[ZendFi] Base URL: {self.base_url}")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": f"langchain-zendfi/{SDK_VERSION}",
                    "X-ZendFi-SDK": f"langchain-python/{SDK_VERSION}",
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
        """
        Make HTTP request to ZendFi API with retry logic.
        
        Implements exponential backoff for transient failures.
        """
        client = await self._get_client()
        
        headers = {}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries):
            try:
                if self.debug:
                    print(f"[ZendFi] {method} {endpoint} (attempt {attempt + 1})")
                    if data:
                        # Redact sensitive fields
                        safe_data = {k: v for k, v in data.items() 
                                     if k not in ['pin', 'signature', 'session_token']}
                        print(f"[ZendFi] Request: {safe_data}")
                
                if method.upper() == "GET":
                    response = await client.get(endpoint, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(endpoint, json=data, headers=headers)
                elif method.upper() == "DELETE":
                    response = await client.delete(endpoint, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                if self.debug:
                    print(f"[ZendFi] Response ({response.status_code})")
                
                # Handle error responses
                if response.status_code >= 400:
                    await self._handle_error_response(response, endpoint)
                
                # Parse successful response
                if response.text:
                    return response.json()
                return {}
                
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 0.5 * (2 ** attempt)  # Exponential backoff
                    if self.debug:
                        print(f"[ZendFi] Transient error, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                continue
            
            except ZendFiAPIError:
                raise
            
            except Exception as e:
                raise ZendFiAPIError(f"Unexpected error: {str(e)}")
        
        raise ZendFiAPIError(f"Request failed after {self.max_retries} attempts: {last_error}")
    
    async def _handle_error_response(self, response: httpx.Response, endpoint: str) -> None:
        """Parse error response and raise appropriate exception."""
        try:
            error_data = response.json() if response.text else {}
        except Exception:
            error_data = {}
        
        message = error_data.get("message") or error_data.get("error") or "Unknown error"
        error_code = error_data.get("code") or error_data.get("error_code")
        details = error_data.get("details")
        
        status = response.status_code
        
        if status == 401:
            raise AuthenticationError(message, status, error_code)
        elif status == 404:
            if "session" in message.lower() or "session" in endpoint.lower():
                raise SessionKeyNotFoundError(message, status, error_code)
            raise ZendFiAPIError(message, status, error_code)
        elif status == 429:
            raise RateLimitError(message, status, error_code)
        elif status == 400:
            raise ValidationError(message, status, error_code, details)
        elif error_code == "INSUFFICIENT_BALANCE":
            raise InsufficientBalanceError(message, status, error_code)
        elif error_code == "SESSION_EXPIRED":
            raise SessionKeyExpiredError(message, status, error_code)
        else:
            raise ZendFiAPIError(message, status, error_code, details)
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    # ============================================
    # Agent Sessions API (Recommended for LangChain)
    # ============================================
    
    async def create_agent_session(
        self,
        agent_id: str,
        user_wallet: str,
        limits: Optional[SessionLimits] = None,
        agent_name: Optional[str] = None,
        duration_hours: int = 24,
        allowed_merchants: Optional[List[str]] = None,
    ) -> AgentSession:
        """
        Create an agent session with spending limits.
        
        This is the RECOMMENDED approach for LangChain agents. No client-side
        cryptography required - the server manages session tokens.
        
        Args:
            agent_id: Unique identifier for the agent
            user_wallet: User's Solana wallet address
            limits: Spending limits (uses defaults if not provided)
            agent_name: Human-readable agent name
            duration_hours: Session duration (1-168 hours, default: 24)
            allowed_merchants: Restrict to specific merchant IDs
            
        Returns:
            AgentSession with session_token for API calls
            
        Example:
            >>> session = await client.create_agent_session(
            ...     agent_id="shopping-agent",
            ...     user_wallet="7xKNH...",
            ...     limits=SessionLimits(max_per_day=50.0),
            ... )
            >>> print(f"Token: {session.session_token}")
        """
        limits = limits or SessionLimits()
        
        response = await self._request("POST", "/api/v1/ai/sessions", {
            "agent_id": agent_id,
            "agent_name": agent_name or f"LangChain Agent ({agent_id})",
            "user_wallet": user_wallet,
            "limits": {
                "max_per_transaction": limits.max_per_transaction,
                "max_per_day": limits.max_per_day,
                "max_per_week": limits.max_per_week,
                "max_per_month": limits.max_per_month,
                "require_approval_above": limits.require_approval_above,
            },
            "allowed_merchants": allowed_merchants,
            "duration_hours": duration_hours,
        })
        
        session = AgentSession(
            id=response["id"],
            session_token=response["session_token"],
            agent_id=response["agent_id"],
            agent_name=response.get("agent_name"),
            user_wallet=response["user_wallet"],
            limits=SessionLimits(
                max_per_transaction=response["limits"].get("max_per_transaction", 1000),
                max_per_day=response["limits"].get("max_per_day", 5000),
                max_per_week=response["limits"].get("max_per_week", 20000),
                max_per_month=response["limits"].get("max_per_month", 50000),
                require_approval_above=response["limits"].get("require_approval_above", 500),
            ),
            is_active=response["is_active"],
            created_at=response["created_at"],
            expires_at=response["expires_at"],
            remaining_today=response.get("remaining_today", limits.max_per_day),
            remaining_this_week=response.get("remaining_this_week", limits.max_per_week),
            remaining_this_month=response.get("remaining_this_month", limits.max_per_month),
            pkp_address=response.get("pkp_address"),
        )
        
        # Cache the session
        self._cached_session = session
        self._session_agent_id = agent_id
        
        if self.debug:
            print(f"[ZendFi] Created agent session: {session.id}")
            print(f"[ZendFi] Daily limit: ${limits.max_per_day}")
        
        return session
    
    async def get_agent_session(self, session_id: str) -> AgentSession:
        """
        Get details of an agent session.
        
        Args:
            session_id: UUID of the session
            
        Returns:
            AgentSession with current limits and spending
        """
        response = await self._request("GET", f"/api/v1/ai/sessions/{session_id}")
        
        return AgentSession(
            id=response["id"],
            session_token=response["session_token"],
            agent_id=response["agent_id"],
            agent_name=response.get("agent_name"),
            user_wallet=response["user_wallet"],
            limits=SessionLimits(
                max_per_transaction=response["limits"].get("max_per_transaction", 1000),
                max_per_day=response["limits"].get("max_per_day", 5000),
                max_per_week=response["limits"].get("max_per_week", 20000),
                max_per_month=response["limits"].get("max_per_month", 50000),
                require_approval_above=response["limits"].get("require_approval_above", 500),
            ),
            is_active=response["is_active"],
            created_at=response["created_at"],
            expires_at=response["expires_at"],
            remaining_today=response.get("remaining_today", 0),
            remaining_this_week=response.get("remaining_this_week", 0),
            remaining_this_month=response.get("remaining_this_month", 0),
        )
    
    async def revoke_agent_session(self, session_id: str) -> None:
        """
        Revoke an agent session.
        
        Args:
            session_id: UUID of the session to revoke
        """
        await self._request("POST", f"/api/v1/ai/sessions/{session_id}/revoke")
        
        # Clear cache if this was the cached session
        if self._cached_session and self._cached_session.id == session_id:
            self._cached_session = None
    
    # ============================================
    # Smart Payments API
    # ============================================
    
    async def smart_payment(
        self,
        agent_id: str,
        user_wallet: str,
        amount_usd: float,
        description: Optional[str] = None,
        session_token: Optional[str] = None,
        token: str = "USDC",
        auto_gasless: bool = True,
        merchant_id: Optional[str] = None,
        instant_settlement: bool = False,
        enable_escrow: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> SmartPaymentResult:
        """
        Execute an AI-powered smart payment.
        
        Smart payments automatically:
        - Detect if gasless transaction is needed
        - Apply PPP pricing adjustments
        - Route through optimal payment path
        - Generate receipts
        
        Args:
            agent_id: Identifier for the agent making the payment
            user_wallet: Payer's Solana wallet address
            amount_usd: Amount in USD
            description: Payment description
            session_token: Session token for spending limit enforcement
            token: Token to use (default: USDC)
            auto_gasless: Auto-detect if gasless is needed
            merchant_id: Target merchant ID
            instant_settlement: Enable instant payout
            enable_escrow: Hold funds in escrow
            metadata: Additional data to attach
            idempotency_key: Prevent duplicate payments
            
        Returns:
            SmartPaymentResult with transaction details
            
        Example:
            >>> result = await client.smart_payment(
            ...     agent_id="shopping-agent",
            ...     user_wallet="7xKNH...",
            ...     amount_usd=5.00,
            ...     description="Premium subscription",
            ... )
            >>> print(f"Payment: {result.payment_id}")
            >>> print(f"Signature: {result.transaction_signature}")
        """
        if not idempotency_key:
            idempotency_key = f"pay_{uuid.uuid4().hex[:16]}"
        
        # Use cached session token if available
        if not session_token and self._cached_session:
            session_token = self._cached_session.session_token
        
        response = await self._request(
            "POST",
            "/api/v1/ai/smart-payment",
            {
                "agent_id": agent_id,
                "user_wallet": user_wallet,
                "amount_usd": amount_usd,
                "description": description,
                "session_token": session_token,
                "token": token,
                "auto_detect_gasless": auto_gasless,
                "merchant_id": merchant_id,
                "instant_settlement": instant_settlement,
                "enable_escrow": enable_escrow,
                "metadata": metadata,
            },
            idempotency_key=idempotency_key,
        )
        
        result = SmartPaymentResult(
            payment_id=response["payment_id"],
            status=response["status"],
            amount_usd=response.get("amount_usd", amount_usd),
            gasless_used=response.get("gasless_used", False),
            settlement_complete=response.get("settlement_complete", False),
            receipt_url=response.get("receipt_url", ""),
            next_steps=response.get("next_steps", ""),
            created_at=response.get("created_at", ""),
            transaction_signature=response.get("transaction_signature"),
            unsigned_transaction=response.get("unsigned_transaction"),
            requires_signature=response.get("requires_signature", False),
            submit_url=response.get("submit_url"),
            escrow_id=response.get("escrow_id"),
            confirmed_in_ms=response.get("confirmed_in_ms"),
        )
        
        if self.debug:
            print(f"[ZendFi] Payment: {result.payment_id} - {result.status}")
            if result.transaction_signature:
                print(f"[ZendFi] Signature: {result.transaction_signature[:20]}...")
        
        return result
    
    async def submit_signed_payment(
        self,
        payment_id: str,
        signed_transaction: str,
    ) -> SmartPaymentResult:
        """
        Submit a signed transaction for device-bound payments.
        
        Args:
            payment_id: UUID of the payment
            signed_transaction: Base64 encoded signed transaction
            
        Returns:
            Updated SmartPaymentResult with confirmation
        """
        response = await self._request(
            "POST",
            f"/api/v1/ai/payments/{payment_id}/submit-signed",
            {"signed_transaction": signed_transaction},
        )
        
        return SmartPaymentResult(
            payment_id=response["payment_id"],
            status=response["status"],
            amount_usd=response.get("amount_usd", 0),
            gasless_used=response.get("gasless_used", False),
            settlement_complete=response.get("settlement_complete", False),
            receipt_url=response.get("receipt_url", ""),
            next_steps=response.get("next_steps", ""),
            created_at=response.get("created_at", ""),
            transaction_signature=response.get("transaction_signature"),
            confirmed_in_ms=response.get("confirmed_in_ms"),
        )
    
    # ============================================
    # Session Keys API (Device-Bound)
    # ============================================
    
    async def create_session_key(
        self,
        user_wallet: str,
        agent_id: str,
        limit_usdc: float,
        duration_days: int = 7,
        agent_name: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
    ) -> SessionKeyResult:
        """
        Create a device-bound session key.
        
        Note: This creates a server-assisted session key. For full client-side
        device-bound keys with Lit Protocol MPC, use the TypeScript SDK.
        For LangChain agents, we recommend using create_agent_session() instead.
        
        Args:
            user_wallet: User's main Solana wallet
            agent_id: Agent identifier
            limit_usdc: Spending limit in USDC
            duration_days: Validity period (1-30 days)
            agent_name: Human-readable name
            device_fingerprint: Client device fingerprint
            
        Returns:
            SessionKeyResult with session_key_id
        """
        # Generate device fingerprint if not provided
        if not device_fingerprint:
            device_fingerprint = hashlib.sha256(
                f"{user_wallet}:{agent_id}:{os.getenv('USER', 'langchain')}:{time.time()}".encode()
            ).hexdigest()[:32]
        
        response = await self._request("POST", "/api/v1/ai/session-keys/device-bound/create", {
            "user_wallet": user_wallet,
            "agent_id": agent_id,
            "agent_name": agent_name or f"LangChain Agent ({agent_id})",
            "limit_usdc": limit_usdc,
            "duration_days": duration_days,
            "device_fingerprint": device_fingerprint,
        })
        
        result = SessionKeyResult(
            session_key_id=response["session_key_id"],
            agent_id=response["agent_id"],
            agent_name=response.get("agent_name"),
            session_wallet=response["session_wallet"],
            limit_usdc=response["limit_usdc"],
            expires_at=response["expires_at"],
            cross_app_compatible=response.get("cross_app_compatible", True),
            requires_client_signing=response.get("requires_client_signing", True),
            mode=response.get("mode", "device_bound"),
        )
        
        # Cache for automatic use
        self._session_key_id = result.session_key_id
        self._session_wallet = result.session_wallet
        self._session_agent_id = result.agent_id
        
        if self.debug:
            print(f"[ZendFi] Created session key: {result.session_key_id}")
            print(f"[ZendFi] Session wallet: {result.session_wallet}")
        
        return result
    
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
            raise SessionKeyNotFoundError(
                "No session key ID provided and none cached. "
                "Create a session key first."
            )
        
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
    # Pricing API
    # ============================================
    
    async def get_ppp_factor(self, country_code: str) -> PPPFactor:
        """
        Get PPP (Purchasing Power Parity) factor for a country.
        
        Args:
            country_code: ISO 3166-1 alpha-2 code (e.g., "BR", "IN")
            
        Returns:
            PPPFactor with adjustment percentage
        """
        response = await self._request("POST", "/api/v1/ai/pricing/ppp-factor", {
            "country_code": country_code.upper(),
        })
        
        return PPPFactor(
            country_code=response["country_code"],
            country_name=response["country_name"],
            ppp_factor=response["ppp_factor"],
            currency_code=response["currency_code"],
            adjustment_percentage=response["adjustment_percentage"],
        )
    
    async def get_pricing_suggestion(
        self,
        agent_id: str,
        base_price: float,
        location_country: Optional[str] = None,
        context: Optional[str] = None,
        enable_ppp: bool = True,
        max_discount_percent: float = 50.0,
    ) -> PricingSuggestion:
        """
        Get AI-powered pricing suggestion.
        
        Args:
            agent_id: Agent identifier
            base_price: Original price in USD
            location_country: Customer's country code
            context: Context hint (e.g., "first-time", "loyal")
            enable_ppp: Apply PPP adjustments
            max_discount_percent: Maximum discount allowed
            
        Returns:
            PricingSuggestion with reasoning
        """
        user_profile = {}
        if location_country:
            user_profile["location_country"] = location_country
        if context:
            user_profile["context"] = context
        
        response = await self._request("POST", "/api/v1/ai/pricing/suggest", {
            "agent_id": agent_id,
            "base_price": base_price,
            "currency": "USD",
            "user_profile": user_profile if user_profile else None,
            "ppp_config": {
                "enabled": enable_ppp,
                "max_discount_percent": max_discount_percent,
            } if enable_ppp else None,
        })
        
        return PricingSuggestion(
            suggested_amount=response["suggested_amount"],
            min_amount=response["min_amount"],
            max_amount=response["max_amount"],
            currency=response["currency"],
            reasoning=response["reasoning"],
            ppp_adjusted=response["ppp_adjusted"],
            adjustment_factor=response.get("adjustment_factor"),
        )
    
    # ============================================
    # Marketplace API
    # ============================================
    
    async def search_marketplace(
        self,
        service_type: str,
        max_price: Optional[float] = None,
        min_reputation: float = 0.0,
    ) -> List[AgentProvider]:
        """
        Search for service providers in the agent marketplace.
        
        Queries the ZendFi Agent Registry for providers offering
        specific services at competitive prices.
        
        Args:
            service_type: Type of service (e.g., 'gpt4-tokens', 'image-generation')
            max_price: Maximum price per unit filter
            min_reputation: Minimum reputation score (0-5)
            
        Returns:
            List of matching providers sorted by price
        """
        try:
            response = await self._request("GET", f"/api/v1/marketplace/providers?service_type={service_type}")
            
            providers = []
            for item in response.get("providers", []):
                provider = AgentProvider(
                    agent_id=item["agent_id"],
                    agent_name=item["agent_name"],
                    service_type=item["service_type"],
                    price_per_unit=item["price_per_unit"],
                    wallet=item["wallet"],
                    reputation=item.get("reputation", 4.0),
                    description=item.get("description"),
                    available=item.get("available", True),
                )
                
                # Apply filters
                if max_price is not None and provider.price_per_unit > max_price:
                    continue
                if provider.reputation < min_reputation:
                    continue
                if not provider.available:
                    continue
                
                providers.append(provider)
            
            # Sort by price
            providers.sort(key=lambda p: p.price_per_unit)
            return providers
            
        except ZendFiAPIError as e:
            # If marketplace API returns 404, it may not be enabled
            if e.status_code == 404:
                if self.debug:
                    print("[ZendFi] Marketplace API not available")
                return []
            raise
    
    async def get_provider(self, agent_id: str) -> Optional[AgentProvider]:
        """
        Get a specific provider by agent ID.
        
        Args:
            agent_id: The agent's unique identifier
            
        Returns:
            AgentProvider if found, None otherwise
        """
        try:
            response = await self._request("GET", f"/api/v1/marketplace/providers/{agent_id}")
            
            return AgentProvider(
                agent_id=response["agent_id"],
                agent_name=response["agent_name"],
                service_type=response["service_type"],
                price_per_unit=response["price_per_unit"],
                wallet=response["wallet"],
                reputation=response.get("reputation", 4.0),
                description=response.get("description"),
                available=response.get("available", True),
            )
        except ZendFiAPIError as e:
            if e.status_code == 404:
                return None
            raise
    
    # ============================================
    # Convenience Methods
    # ============================================
    
    async def ensure_session(
        self,
        agent_id: str = "langchain-agent",
        user_wallet: Optional[str] = None,
        limits: Optional[SessionLimits] = None,
    ) -> AgentSession:
        """
        Ensure an agent session exists, creating one if needed.
        
        Args:
            agent_id: Agent identifier
            user_wallet: User's wallet (uses ZENDFI_USER_WALLET env var if not set)
            limits: Spending limits
            
        Returns:
            Active AgentSession
        """
        # Return cached session if still valid
        if self._cached_session and self._cached_session.is_active:
            return self._cached_session
        
        wallet = user_wallet or os.getenv("ZENDFI_USER_WALLET")
        if not wallet:
            raise ValueError(
                "User wallet required. Set ZENDFI_USER_WALLET environment variable "
                "or pass user_wallet parameter."
            )
        
        return await self.create_agent_session(
            agent_id=agent_id,
            user_wallet=wallet,
            limits=limits or SessionLimits(max_per_day=100.0),
        )
    
    async def pay(
        self,
        amount_usd: float,
        recipient: str,
        description: str,
        agent_id: str = "langchain-agent",
        idempotency_key: Optional[str] = None,
    ) -> SmartPaymentResult:
        """
        Simple payment method - creates session if needed and pays.
        
        Args:
            amount_usd: Amount in USD
            recipient: Recipient wallet address
            description: Payment description
            agent_id: Agent identifier
            idempotency_key: Prevent duplicate payments
            
        Returns:
            SmartPaymentResult
        """
        # Ensure we have a session
        session = await self.ensure_session(agent_id=agent_id)
        
        return await self.smart_payment(
            agent_id=agent_id,
            user_wallet=recipient,
            amount_usd=amount_usd,
            description=description,
            session_token=session.session_token,
            idempotency_key=idempotency_key,
        )
    
    # Legacy method for backward compatibility
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
        Execute a payment (legacy method, use smart_payment instead).
        
        Maintained for backward compatibility with existing code.
        Internally uses smart_payment API.
        """
        agent_id = self._session_agent_id or "langchain-agent"
        
        result = await self.smart_payment(
            agent_id=agent_id,
            user_wallet=recipient,
            amount_usd=amount,
            description=description,
            token=token,
            idempotency_key=idempotency_key,
        )
        
        return PaymentResult(
            payment_id=result.payment_id,
            signature=result.transaction_signature or "",
            status=result.status,
            amount=amount,
            recipient=recipient,
        )


# ============================================
# Module-level convenience functions
# ============================================

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
