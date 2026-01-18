"""
LangChain ZendFi Integration
============================

Enable LangChain agents to make autonomous cryptocurrency payments on Solana.

This package provides production-ready LangChain tools for:
- **Autonomous Payments**: Session keys with spending limits
- **Non-Custodial Security**: Device-bound keys, never exposed to backend
- **Gasless Transactions**: Backend handles all Solana fees
- **Marketplace Integration**: Discover and pay agent service providers
- **PPP Pricing**: Fair global pricing with purchasing power adjustments

Quick Start:
    >>> from langchain_zendfi import create_zendfi_tools
    >>> from langchain.agents import create_tool_calling_agent
    >>> 
    >>> # Create all ZendFi tools
    >>> tools = create_zendfi_tools(session_limit_usd=25.0)
    >>> 
    >>> # Add to your agent
    >>> agent = create_tool_calling_agent(llm, tools)
    >>> 
    >>> # Agent can now make autonomous payments!
    >>> agent.invoke({"input": "Pay $0.50 to ProviderWallet123 for tokens"})

Session Keys (Device-Bound Non-Custodial):
    >>> from langchain_zendfi import ZendFiClient
    >>> from langchain_zendfi.session_keys import CreateSessionKeyOptions
    >>> 
    >>> client = ZendFiClient()
    >>> 
    >>> # Create session key with PIN encryption
    >>> result = await client.session_keys.create(CreateSessionKeyOptions(
    ...     user_wallet="7xKNH...",
    ...     agent_id="shopping-agent",
    ...     limit_usdc=100.0,
    ...     pin="123456",
    ... ))
    >>> 
    >>> # Unlock for signing
    >>> client.session_keys.unlock(result.session_key_id, "123456")

Autonomous Mode:
    >>> from langchain_zendfi.autonomy import EnableAutonomyRequest
    >>> 
    >>> # Enable autonomous payments
    >>> delegate = await client.autonomy.enable(
    ...     session_key_id=result.session_key_id,
    ...     request=EnableAutonomyRequest(
    ...         max_amount_usd=100.0,
    ...         duration_hours=24,
    ...         delegation_signature=signature,
    ...     ),
    ... )

Environment Variables:
    ZENDFI_API_KEY: Your ZendFi API key (required)
    ZENDFI_USER_WALLET: User wallet for session creation
    ZENDFI_MODE: 'test' (devnet) or 'live' (mainnet), default: 'test'

For more information, see: https://docs.zendfi.tech/langchain
"""

__version__ = "0.2.0"  # Updated with session keys + autonomy
__author__ = "ZendFi Team"
__email__ = "support@zendfi.tech"

# Core tools - the main export
from langchain_zendfi.tools import (
    ZendFiPaymentTool,
    ZendFiMarketplaceTool,
    ZendFiBalanceTool,
    ZendFiCreateSessionTool,
    ZendFiAgentSessionTool,
    ZendFiPricingTool,
    create_zendfi_tools,
    create_minimal_zendfi_tools,
)

# Client for direct API access
from langchain_zendfi.client import (
    ZendFiClient,
    ZendFiMode,
    SessionKeyResult,
    SessionKeyStatus,
    PaymentResult,
    SmartPaymentResult,
    AgentSession,
    SessionLimits,
    PPPFactor,
    PricingSuggestion,
    AgentProvider,
    ZendFiAPIError,
    AuthenticationError,
    InsufficientBalanceError,
    SessionKeyExpiredError,
    SessionKeyNotFoundError,
    RateLimitError,
    ValidationError,
    get_zendfi_client,
    reset_zendfi_client,
)

# Utility functions
from langchain_zendfi.utils import (
    generate_idempotency_key,
    format_solana_address,
    format_usd,
    validate_solana_address,
    SessionKeyCache,
)

# Session Keys (Device-Bound Non-Custodial)
from langchain_zendfi.session_keys import (
    CreateSessionKeyOptions,
    SessionKeyResult as DeviceBoundSessionKeyResult,
    SessionKeyInfo,
    DeviceBoundSessionKey,
    SessionKeysManager,
)

# Autonomy (Autonomous Agent Signing)
from langchain_zendfi.autonomy import (
    EnableAutonomyRequest,
    AutonomousDelegate,
    AutonomyStatus,
    AutonomyManager,
    calculate_expires_at,
)

# Crypto Primitives (for advanced usage)
from langchain_zendfi.crypto import (
    generate_keypair,
    SessionKeypair,
    SessionKeyCrypto,
    DeviceFingerprintGenerator,
    EncryptedSessionKey,
    create_delegation_message,
    sign_message,
    sign_message_base64,
    base58_encode,
    base58_decode,
    verify_dependencies,
    # Lit Protocol (for autonomous signing)
    encrypt_keypair_with_lit,
    LitEncryptionResult,
    HAS_NACL,
    HAS_CRYPTOGRAPHY,
)

# Public API
__all__ = [
    # Version info
    "__version__",
    
    # LangChain Tools (primary exports)
    "ZendFiPaymentTool",
    "ZendFiMarketplaceTool",
    "ZendFiBalanceTool",
    "ZendFiCreateSessionTool",
    "ZendFiAgentSessionTool",
    "ZendFiPricingTool",
    "create_zendfi_tools",
    "create_minimal_zendfi_tools",
    
    # Client
    "ZendFiClient",
    "ZendFiMode",
    "SessionKeyResult",
    "SessionKeyStatus",
    "PaymentResult",
    "SmartPaymentResult",
    "AgentSession",
    "SessionLimits",
    "PPPFactor",
    "PricingSuggestion",
    "AgentProvider",
    "get_zendfi_client",
    "reset_zendfi_client",
    
    # Session Keys (Device-Bound)
    "CreateSessionKeyOptions",
    "DeviceBoundSessionKeyResult",
    "SessionKeyInfo",
    "DeviceBoundSessionKey",
    "SessionKeysManager",
    
    # Autonomy
    "EnableAutonomyRequest",
    "AutonomousDelegate",
    "AutonomyStatus",
    "AutonomyManager",
    "calculate_expires_at",
    
    # Crypto Primitives
    "generate_keypair",
    "SessionKeypair",
    "SessionKeyCrypto",
    "DeviceFingerprintGenerator",
    "EncryptedSessionKey",
    "create_delegation_message",
    "sign_message",
    "sign_message_base64",
    "base58_encode",
    "base58_decode",
    "verify_dependencies",
    # Lit Protocol
    "encrypt_keypair_with_lit",
    "LitEncryptionResult",
    "HAS_NACL",
    "HAS_CRYPTOGRAPHY",
    
    # Errors
    "ZendFiAPIError",
    "AuthenticationError",
    "InsufficientBalanceError",
    "SessionKeyExpiredError",
    "SessionKeyNotFoundError",
    "RateLimitError",
    "ValidationError",
    
    # Utilities
    "generate_idempotency_key",
    "format_solana_address",
    "format_usd",
    "validate_solana_address",
    "SessionKeyCache",
]
