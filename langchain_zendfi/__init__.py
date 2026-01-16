"""
LangChain ZendFi Integration
============================

Enable LangChain agents to make autonomous cryptocurrency payments on Solana.

This package provides production-ready LangChain tools for:
- **Autonomous Payments**: Session keys with spending limits
- **Non-Custodial Security**: Device-bound keys, never exposed to backend
- **Gasless Transactions**: Backend handles all Solana fees
- **Marketplace Integration**: Discover and pay agent service providers

Quick Start:
    >>> from langchain_zendfi import ZendFiPaymentTool, ZendFiBalanceTool
    >>> from langchain.agents import create_tool_calling_agent
    >>> 
    >>> # Create tools with $10 spending limit
    >>> payment_tool = ZendFiPaymentTool(session_limit_usd=10.0)
    >>> balance_tool = ZendFiBalanceTool(session_limit_usd=10.0)
    >>> 
    >>> # Add to your agent
    >>> agent = create_tool_calling_agent(llm, [payment_tool, balance_tool])
    >>> 
    >>> # Agent can now make autonomous payments!
    >>> agent.invoke({"input": "Pay $0.50 to ProviderWallet123 for tokens"})

Environment Variables:
    ZENDFI_API_KEY: Your ZendFi API key (required)
    ZENDFI_USER_WALLET: Default user wallet for auto-session creation
    ZENDFI_MODE: 'test' (devnet) or 'live' (mainnet), default: 'test'

For more information, see: https://docs.zendfi.com/langchain
"""

__version__ = "0.1.0"
__author__ = "ZendFi Team"
__email__ = "support@zendfi.com"

# Core tools - the main export
from langchain_zendfi.tools import (
    ZendFiPaymentTool,
    ZendFiMarketplaceTool,
    ZendFiBalanceTool,
    ZendFiCreateSessionTool,
    create_zendfi_tools,
)

# Client for direct API access
from langchain_zendfi.client import (
    ZendFiClient,
    ZendFiMode,
    SessionKeyResult,
    SessionKeyStatus,
    PaymentResult,
    AgentProvider,
    ZendFiAPIError,
    InsufficientBalanceError,
    SessionKeyExpiredError,
    SessionKeyNotFoundError,
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

# Public API
__all__ = [
    # Version info
    "__version__",
    
    # LangChain Tools (primary exports)
    "ZendFiPaymentTool",
    "ZendFiMarketplaceTool",
    "ZendFiBalanceTool",
    "ZendFiCreateSessionTool",
    "create_zendfi_tools",
    
    # Client
    "ZendFiClient",
    "ZendFiMode",
    "SessionKeyResult",
    "SessionKeyStatus",
    "PaymentResult",
    "AgentProvider",
    "get_zendfi_client",
    "reset_zendfi_client",
    
    # Errors
    "ZendFiAPIError",
    "InsufficientBalanceError",
    "SessionKeyExpiredError",
    "SessionKeyNotFoundError",
    
    # Utilities
    "generate_idempotency_key",
    "format_solana_address",
    "format_usd",
    "validate_solana_address",
    "SessionKeyCache",
]
