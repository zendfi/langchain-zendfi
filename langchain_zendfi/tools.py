"""
LangChain Tool Implementations for ZendFi
==========================================
Production-ready LangChain tools for autonomous cryptocurrency payments.

These tools follow LangChain best practices:
- Pydantic schemas for function calling
- Both sync and async implementations
- Comprehensive error handling
- Rich output formatting

Tools provided:
- ZendFiPaymentTool: Execute autonomous crypto payments
- ZendFiMarketplaceTool: Search for agent service providers
- ZendFiBalanceTool: Check session key balance and limits
- ZendFiCreateSessionTool: Create a new session key
- ZendFiAgentSessionTool: Create agent session (recommended)
- ZendFiPricingTool: Get PPP-adjusted pricing suggestions
"""

from typing import Optional, Type, Any, ClassVar, List
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun
import asyncio
import os

from langchain_zendfi.client import (
    ZendFiClient,
    ZendFiAPIError,
    AuthenticationError,
    InsufficientBalanceError,
    SessionKeyExpiredError,
    SessionKeyNotFoundError,
    RateLimitError,
    ValidationError,
    SessionLimits,
)


# ============================================
# Input Schemas (Pydantic v2 for LangChain)
# ============================================

class PaymentInput(BaseModel):
    """Input schema for executing a cryptocurrency payment."""
    
    recipient: str = Field(
        description="Solana wallet address of the recipient. "
                    "This is where the payment will be sent."
    )
    amount_usd: float = Field(
        description="Amount to pay in USD. For example, 1.50 for $1.50. "
                    "Must be within your session key's spending limit."
    )
    description: str = Field(
        description="Description of what the payment is for. "
                    "For example, '10 GPT-4 tokens' or 'Image generation service'."
    )


class MarketplaceSearchInput(BaseModel):
    """Input schema for searching the agent marketplace."""
    
    service_type: str = Field(
        description="Type of service to search for. Common types: "
                    "'gpt4-tokens', 'image-generation', 'code-review', 'data-analysis'."
    )
    max_price: Optional[float] = Field(
        default=None,
        description="Optional maximum price per unit to filter by. "
                    "For example, 0.10 for services costing at most $0.10/unit."
    )
    min_reputation: float = Field(
        default=4.0,
        description="Minimum provider reputation score (0-5). Default is 4.0."
    )


class BalanceInput(BaseModel):
    """Input schema for checking balance (no inputs required)."""
    pass


class CreateSessionInput(BaseModel):
    """Input schema for creating a new session key."""
    
    agent_id: str = Field(
        default="langchain-agent",
        description="Unique identifier for this agent. Used for tracking and cross-app compatibility."
    )
    limit_usd: float = Field(
        default=10.0,
        description="Maximum spending limit in USD for this session key."
    )
    duration_days: int = Field(
        default=7,
        description="How many days the session key should be valid (1-30)."
    )


class AgentSessionInput(BaseModel):
    """Input schema for creating an agent session (recommended approach)."""
    
    agent_id: str = Field(
        default="langchain-agent",
        description="Unique identifier for this agent."
    )
    max_per_day: float = Field(
        default=100.0,
        description="Maximum spending per day in USD."
    )
    max_per_transaction: float = Field(
        default=50.0,
        description="Maximum per-transaction limit in USD."
    )
    duration_hours: int = Field(
        default=24,
        description="Session duration in hours (1-168)."
    )


class PricingInput(BaseModel):
    """Input schema for getting pricing suggestions."""
    
    base_price: float = Field(
        description="Original price in USD to get suggestions for."
    )
    country_code: Optional[str] = Field(
        default=None,
        description="ISO 3166-1 alpha-2 country code (e.g., 'BR', 'IN', 'NG') for PPP adjustment."
    )


# ============================================
# Tool Implementations
# ============================================

class ZendFiPaymentTool(BaseTool):
    """
    Tool for making autonomous cryptocurrency payments on Solana.
    
    This tool enables LangChain agents to execute payments without
    requiring user approval for each transaction. Uses session keys
    with spending limits for security.
    
    Features:
    - Autonomous: No per-transaction user approval needed
    - Gasless: Backend pays all Solana transaction fees
    - Instant: ~400ms confirmation time
    - Non-custodial: Private keys never leave user's device
    
    Example:
        >>> from langchain_zendfi import ZendFiPaymentTool
        >>> tool = ZendFiPaymentTool(session_limit_usd=10.0)
        >>> result = tool.invoke({
        ...     "recipient": "ProviderWallet1234",
        ...     "amount_usd": 1.50,
        ...     "description": "15 GPT-4 tokens"
        ... })
    """
    
    name: str = "make_crypto_payment"
    description: str = """Execute a cryptocurrency payment on Solana using USDC.

Use this tool to pay another agent or wallet for services or goods.
The agent can spend up to its session key limit autonomously.

Arguments:
- recipient: Solana wallet address to send payment to
- amount_usd: Amount in USD (e.g., 1.50 for $1.50)  
- description: What you're paying for

Returns transaction confirmation with signature.

Important: Check your balance first with check_payment_balance if unsure about available funds."""
    
    args_schema: Type[BaseModel] = PaymentInput
    
    # Configuration
    api_key: Optional[str] = None
    mode: str = "test"
    session_limit_usd: float = 10.0
    debug: bool = False
    
    # Internal client (lazy initialization)
    _client: Optional[ZendFiClient] = None
    
    model_config: ClassVar[dict] = {"arbitrary_types_allowed": True}
    
    def _get_client(self) -> ZendFiClient:
        """Get or create ZendFi client."""
        if self._client is None:
            self._client = ZendFiClient(
                api_key=self.api_key,
                mode=self.mode,
                auto_create_session=True,
                session_limit_usd=self.session_limit_usd,
                debug=self.debug,
            )
        return self._client
    
    def _run(
        self,
        recipient: str,
        amount_usd: float,
        description: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute a payment synchronously.
        
        Args:
            recipient: Wallet address to pay
            amount_usd: Amount in USD
            description: Payment description
            run_manager: LangChain callback manager
            
        Returns:
            Human-readable payment confirmation
        """
        # Run async method in sync context
        return asyncio.get_event_loop().run_until_complete(
            self._arun(recipient, amount_usd, description, run_manager=None)
        )
    
    async def _arun(
        self,
        recipient: str,
        amount_usd: float,
        description: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute a payment asynchronously.
        
        Args:
            recipient: Wallet address to pay
            amount_usd: Amount in USD
            description: Payment description
            run_manager: LangChain async callback manager
            
        Returns:
            Human-readable payment confirmation
        """
        try:
            client = self._get_client()
            
            # Use smart_payment API for production
            result = await client.smart_payment(
                agent_id=self._client._session_agent_id or "langchain-agent",
                user_wallet=recipient,
                amount_usd=amount_usd,
                description=description,
            )
            
            # Format transaction signature if available
            sig_display = result.transaction_signature[:20] + "..." if result.transaction_signature else "pending"
            
            output = f"""✅ Payment Successful!

💵 Amount: ${amount_usd:.2f} USD
📬 Recipient: {recipient}
🔗 Transaction: {sig_display}
📝 Description: {description}
🆔 Payment ID: {result.payment_id}
⚡ Status: {result.status}"""

            if result.gasless_used:
                output += "\n🎁 Gasless: Yes (ZendFi paid the network fees)"
            
            if result.receipt_url:
                output += f"\n🧾 Receipt: {result.receipt_url}"
            
            if result.confirmed_in_ms:
                output += f"\n⏱️ Confirmed in: {result.confirmed_in_ms}ms"
            
            return output

        except InsufficientBalanceError as e:
            return f"""❌ Payment Failed: Insufficient Balance

You tried to pay ${amount_usd:.2f} but don't have enough funds.

💡 Tip: Use the check_payment_balance tool to see your remaining balance,
   or create a new session key with a higher limit."""

        except SessionKeyExpiredError as e:
            return f"""❌ Payment Failed: Session Key Expired

Your session key has expired and can no longer be used for payments.

💡 Tip: Create a new session key to continue making payments."""

        except SessionKeyNotFoundError as e:
            return f"""❌ Payment Failed: No Session Key

No session key is configured for this agent.

💡 Tip: A session key will be created automatically on the next attempt,
   or you can create one explicitly with specific limits."""

        except ZendFiAPIError as e:
            return f"""❌ Payment Failed: {str(e)}

Please verify:
- The recipient address is a valid Solana wallet
- You have sufficient balance in your session key
- Your session key hasn't expired"""

        except Exception as e:
            return f"""❌ Unexpected Error: {str(e)}

Please try again or contact support if the issue persists."""


class ZendFiMarketplaceTool(BaseTool):
    """
    Tool for searching the ZendFi agent marketplace.
    
    Enables agents to discover and compare service providers
    before making payments. Returns providers sorted by price
    with reputation scores and wallet addresses.
    
    Example:
        >>> tool = ZendFiMarketplaceTool()
        >>> result = tool.invoke({
        ...     "service_type": "gpt4-tokens",
        ...     "max_price": 0.10
        ... })
    """
    
    name: str = "search_agent_marketplace"
    description: str = """Search for AI agent service providers in the ZendFi marketplace.

Use this tool to find providers before making a payment. Returns:
- Provider name and agent ID
- Price per unit
- Reputation score (0-5 stars)
- Wallet address for payment

Arguments:
- service_type: What you need ('gpt4-tokens', 'image-generation', 'code-review', etc.)
- max_price: Optional price limit per unit
- min_reputation: Minimum reputation score (default: 4.0)

After finding a provider, use make_crypto_payment with their wallet address."""
    
    args_schema: Type[BaseModel] = MarketplaceSearchInput
    
    # Configuration
    api_key: Optional[str] = None
    mode: str = "test"
    debug: bool = False
    
    _client: Optional[ZendFiClient] = None
    
    model_config: ClassVar[dict] = {"arbitrary_types_allowed": True}
    
    def _get_client(self) -> ZendFiClient:
        """Get or create ZendFi client."""
        if self._client is None:
            self._client = ZendFiClient(
                api_key=self.api_key,
                mode=self.mode,
                auto_create_session=False,  # Marketplace search doesn't need session
                debug=self.debug,
            )
        return self._client
    
    def _run(
        self,
        service_type: str,
        max_price: Optional[float] = None,
        min_reputation: float = 4.0,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Search for providers synchronously."""
        return asyncio.get_event_loop().run_until_complete(
            self._arun(service_type, max_price, min_reputation, run_manager=None)
        )
    
    async def _arun(
        self,
        service_type: str,
        max_price: Optional[float] = None,
        min_reputation: float = 4.0,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Search for providers asynchronously."""
        try:
            client = self._get_client()
            providers = await client.search_marketplace(
                service_type=service_type,
                max_price=max_price,
                min_reputation=min_reputation,
            )
            
            if not providers:
                filters = [f"service type '{service_type}'"]
                if max_price:
                    filters.append(f"max price ${max_price:.2f}")
                if min_reputation > 0:
                    filters.append(f"min reputation {min_reputation}")
                    
                return f"""🔍 No providers found matching your criteria:
{', '.join(filters)}

💡 Try:
- Broadening your search (higher max_price or lower min_reputation)
- Checking for alternative service types"""
            
            result = f"""🔍 Found {len(providers)} provider(s) for '{service_type}'

"""
            for i, provider in enumerate(providers, 1):
                stars = "⭐" * int(provider.reputation) + "☆" * (5 - int(provider.reputation))
                result += f"""**{i}. {provider.agent_name}**
   💰 Price: ${provider.price_per_unit:.3f} per unit
   {stars} ({provider.reputation:.1f}/5.0)
   📝 {provider.description or 'No description'}
   💼 Agent ID: {provider.agent_id}
   📬 Wallet: {provider.wallet}

"""
            
            result += """---
To purchase from a provider, use make_crypto_payment with:
- Their wallet address as 'recipient'
- The total amount (price × quantity) as 'amount_usd'"""
            
            return result

        except ZendFiAPIError as e:
            return f"❌ Marketplace search failed: {str(e)}"
        
        except Exception as e:
            return f"❌ Unexpected error: {str(e)}"


class ZendFiBalanceTool(BaseTool):
    """
    Tool for checking session key balance and spending limits.
    
    Returns current balance, amount spent, total limit, and
    expiration information for the agent's session key.
    
    Example:
        >>> tool = ZendFiBalanceTool()
        >>> result = tool.invoke({})
    """
    
    name: str = "check_payment_balance"
    description: str = """Check your current payment balance and session key status.

Returns:
- Remaining balance in USD
- Amount already spent
- Total spending limit
- Session expiration date
- Whether the session is active

Use this before making payments to ensure sufficient funds."""
    
    args_schema: Type[BaseModel] = BalanceInput
    
    # Configuration
    api_key: Optional[str] = None
    mode: str = "test"
    session_limit_usd: float = 10.0
    debug: bool = False
    
    _client: Optional[ZendFiClient] = None
    
    model_config: ClassVar[dict] = {"arbitrary_types_allowed": True}
    
    def _get_client(self) -> ZendFiClient:
        """Get or create ZendFi client."""
        if self._client is None:
            self._client = ZendFiClient(
                api_key=self.api_key,
                mode=self.mode,
                auto_create_session=True,
                session_limit_usd=self.session_limit_usd,
                debug=self.debug,
            )
        return self._client
    
    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Check balance synchronously."""
        return asyncio.get_event_loop().run_until_complete(
            self._arun(run_manager=None)
        )
    
    async def _arun(
        self,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Check balance asynchronously."""
        try:
            client = self._get_client()
            status = await client.get_session_status()
            
            # Calculate percentage remaining
            pct_remaining = (status.remaining_usdc / status.limit_usdc * 100) if status.limit_usdc > 0 else 0
            
            # Status indicator
            status_emoji = "🟢" if status.is_active else "🔴"
            status_text = "Active" if status.is_active else "Inactive"
            
            # Progress bar
            bar_filled = int(pct_remaining / 10)
            bar_empty = 10 - bar_filled
            progress_bar = "█" * bar_filled + "░" * bar_empty
            
            return f"""💰 Session Key Balance

{status_emoji} Status: {status_text}
📊 Balance: ${status.remaining_usdc:.2f} / ${status.limit_usdc:.2f} USD
   [{progress_bar}] {pct_remaining:.0f}% remaining

💸 Spent: ${status.used_amount_usdc:.2f} USD
📅 Expires: {status.expires_at}
   ({status.days_until_expiry} days remaining)

🔑 Session ID: {status.session_key_id}"""

        except SessionKeyNotFoundError:
            return """⚠️ No Session Key Found

A session key hasn't been created yet. One will be created
automatically when you make your first payment.

Or use create_session_key to create one with custom limits."""

        except ZendFiAPIError as e:
            return f"❌ Failed to check balance: {str(e)}"
        
        except Exception as e:
            return f"❌ Unexpected error: {str(e)}"


class ZendFiCreateSessionTool(BaseTool):
    """
    Tool for creating a new session key with custom limits.
    
    Session keys enable autonomous payments with spending caps.
    Use this to set up a new session with specific limits.
    
    Example:
        >>> tool = ZendFiCreateSessionTool()
        >>> result = tool.invoke({
        ...     "agent_id": "shopping-agent",
        ...     "limit_usd": 25.0,
        ...     "duration_days": 14
        ... })
    """
    
    name: str = "create_session_key"
    description: str = """Create a new session key for autonomous payments.

A session key allows you to make payments up to a spending limit
without requiring approval for each transaction.

Arguments:
- agent_id: Identifier for this agent (default: 'langchain-agent')
- limit_usd: Maximum spending limit in USD (default: 10.0)
- duration_days: How long the key is valid, 1-30 days (default: 7)

Returns the session key details including wallet address and limits."""
    
    args_schema: Type[BaseModel] = CreateSessionInput
    
    # Configuration
    api_key: Optional[str] = None
    mode: str = "test"
    user_wallet: Optional[str] = None
    debug: bool = False
    
    _client: Optional[ZendFiClient] = None
    
    model_config: ClassVar[dict] = {"arbitrary_types_allowed": True}
    
    def _get_client(self) -> ZendFiClient:
        """Get or create ZendFi client."""
        if self._client is None:
            self._client = ZendFiClient(
                api_key=self.api_key,
                mode=self.mode,
                auto_create_session=False,
                debug=self.debug,
            )
        return self._client
    
    def _run(
        self,
        agent_id: str = "langchain-agent",
        limit_usd: float = 10.0,
        duration_days: int = 7,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Create session key synchronously."""
        return asyncio.get_event_loop().run_until_complete(
            self._arun(agent_id, limit_usd, duration_days, run_manager=None)
        )
    
    async def _arun(
        self,
        agent_id: str = "langchain-agent",
        limit_usd: float = 10.0,
        duration_days: int = 7,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Create session key asynchronously."""
        try:
            import os
            client = self._get_client()
            user_wallet = self.user_wallet or os.getenv("ZENDFI_USER_WALLET", "demo-wallet")
            
            result = await client.create_session_key(
                user_wallet=user_wallet,
                agent_id=agent_id,
                limit_usdc=limit_usd,
                duration_days=duration_days,
            )
            
            return f"""✅ Session Key Created Successfully!

🔑 Session ID: {result.session_key_id}
📬 Session Wallet: {result.session_wallet}
💰 Spending Limit: ${result.limit_usdc:.2f} USD
📅 Expires: {result.expires_at}
🤖 Agent ID: {result.agent_id}

You can now make autonomous payments up to your spending limit.
Use check_payment_balance to monitor your remaining balance."""

        except ZendFiAPIError as e:
            return f"❌ Failed to create session key: {str(e)}"
        
        except Exception as e:
            return f"❌ Unexpected error: {str(e)}"


class ZendFiAgentSessionTool(BaseTool):
    """
    Tool for creating agent sessions with spending limits (recommended).
    
    Agent sessions are the recommended approach for LangChain agents:
    - No client-side cryptography required
    - Server-managed session tokens
    - Flexible spending limits (per-transaction, daily, weekly, monthly)
    
    Example:
        >>> tool = ZendFiAgentSessionTool()
        >>> result = tool.invoke({
        ...     "agent_id": "shopping-agent",
        ...     "max_per_day": 50.0,
        ... })
    """
    
    name: str = "create_agent_session"
    description: str = """Create an agent session with spending limits (recommended).

Agent sessions enable autonomous payments with flexible limits:
- Per-transaction limits
- Daily spending caps
- Weekly and monthly limits

This is the recommended approach for LangChain agents.

Arguments:
- agent_id: Unique identifier for this agent
- max_per_day: Daily spending limit in USD (default: 100)
- max_per_transaction: Per-transaction limit in USD (default: 50)
- duration_hours: Session duration (default: 24)

Returns session details including session token."""
    
    args_schema: Type[BaseModel] = AgentSessionInput
    
    # Configuration
    api_key: Optional[str] = None
    mode: str = "test"
    user_wallet: Optional[str] = None
    debug: bool = False
    
    _client: Optional[ZendFiClient] = None
    
    model_config: ClassVar[dict] = {"arbitrary_types_allowed": True}
    
    def _get_client(self) -> ZendFiClient:
        """Get or create ZendFi client."""
        if self._client is None:
            self._client = ZendFiClient(
                api_key=self.api_key,
                mode=self.mode,
                auto_create_session=False,
                debug=self.debug,
            )
        return self._client
    
    def _run(
        self,
        agent_id: str = "langchain-agent",
        max_per_day: float = 100.0,
        max_per_transaction: float = 50.0,
        duration_hours: int = 24,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Create agent session synchronously."""
        return asyncio.get_event_loop().run_until_complete(
            self._arun(agent_id, max_per_day, max_per_transaction, duration_hours, run_manager=None)
        )
    
    async def _arun(
        self,
        agent_id: str = "langchain-agent",
        max_per_day: float = 100.0,
        max_per_transaction: float = 50.0,
        duration_hours: int = 24,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Create agent session asynchronously."""
        try:
            client = self._get_client()
            user_wallet = self.user_wallet or os.getenv("ZENDFI_USER_WALLET")
            
            if not user_wallet:
                return """❌ User wallet not configured.

Please set ZENDFI_USER_WALLET environment variable or configure
the user_wallet parameter on the tool."""
            
            limits = SessionLimits(
                max_per_transaction=max_per_transaction,
                max_per_day=max_per_day,
                max_per_week=max_per_day * 7,
                max_per_month=max_per_day * 30,
            )
            
            result = await client.create_agent_session(
                agent_id=agent_id,
                user_wallet=user_wallet,
                limits=limits,
                duration_hours=duration_hours,
            )
            
            return f"""✅ Agent Session Created Successfully!

🆔 Session ID: {result.id}
🤖 Agent: {result.agent_name or result.agent_id}
📬 Wallet: {result.user_wallet}

💰 Spending Limits:
   • Per Transaction: ${limits.max_per_transaction:.2f}
   • Per Day: ${limits.max_per_day:.2f}
   • Per Week: ${limits.max_per_week:.2f}

📅 Expires: {result.expires_at}

You can now make autonomous payments within your limits.
Use check_payment_balance to monitor spending."""

        except AuthenticationError:
            return """❌ Authentication Failed

Your ZendFi API key is invalid or missing.
Please check your ZENDFI_API_KEY environment variable."""

        except ValidationError as e:
            return f"""❌ Validation Error: {str(e)}

Please check your input parameters."""

        except ZendFiAPIError as e:
            return f"❌ Failed to create session: {str(e)}"
        
        except Exception as e:
            return f"❌ Unexpected error: {str(e)}"


class ZendFiPricingTool(BaseTool):
    """
    Tool for getting PPP-adjusted pricing suggestions.
    
    Enables fair global pricing by adjusting prices based on
    Purchasing Power Parity (PPP) for different countries.
    
    Example:
        >>> tool = ZendFiPricingTool()
        >>> result = tool.invoke({
        ...     "base_price": 10.0,
        ...     "country_code": "BR"
        ... })
    """
    
    name: str = "get_pricing_suggestion"
    description: str = """Get PPP-adjusted pricing suggestion for different countries.

Enables fair global pricing by adjusting for purchasing power.

Arguments:
- base_price: Original price in USD
- country_code: ISO 3166-1 alpha-2 code (e.g., 'BR' for Brazil, 'IN' for India)

Returns:
- Suggested adjusted price
- PPP adjustment factor
- Reasoning for the adjustment"""
    
    args_schema: Type[BaseModel] = PricingInput
    
    # Configuration
    api_key: Optional[str] = None
    mode: str = "test"
    debug: bool = False
    
    _client: Optional[ZendFiClient] = None
    
    model_config: ClassVar[dict] = {"arbitrary_types_allowed": True}
    
    def _get_client(self) -> ZendFiClient:
        """Get or create ZendFi client."""
        if self._client is None:
            self._client = ZendFiClient(
                api_key=self.api_key,
                mode=self.mode,
                auto_create_session=False,
                debug=self.debug,
            )
        return self._client
    
    def _run(
        self,
        base_price: float,
        country_code: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Get pricing suggestion synchronously."""
        return asyncio.get_event_loop().run_until_complete(
            self._arun(base_price, country_code, run_manager=None)
        )
    
    async def _arun(
        self,
        base_price: float,
        country_code: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Get pricing suggestion asynchronously."""
        try:
            client = self._get_client()
            
            # If country code provided, first get PPP factor
            ppp_info = ""
            if country_code:
                try:
                    ppp = await client.get_ppp_factor(country_code)
                    ppp_info = f"""
🌍 PPP Factor for {ppp.country_name}:
   Factor: {ppp.ppp_factor:.2f}
   Adjustment: {ppp.adjustment_percentage:+.0f}%
   Local Currency: {ppp.currency_code}
"""
                except ZendFiAPIError:
                    ppp_info = f"\n⚠️ Could not fetch PPP data for {country_code}\n"
            
            # Get AI pricing suggestion
            suggestion = await client.get_pricing_suggestion(
                agent_id="langchain-pricing",
                base_price=base_price,
                location_country=country_code,
            )
            
            discount = ((base_price - suggestion.suggested_amount) / base_price) * 100 if base_price > 0 else 0
            
            return f"""💰 Pricing Suggestion

📊 Base Price: ${base_price:.2f} USD
✨ Suggested Price: ${suggestion.suggested_amount:.2f} USD
📉 Discount: {discount:.0f}%
{ppp_info}
📝 Reasoning: {suggestion.reasoning}

💡 Price Range:
   Min: ${suggestion.min_amount:.2f}
   Max: ${suggestion.max_amount:.2f}"""

        except ZendFiAPIError as e:
            return f"❌ Pricing suggestion failed: {str(e)}"
        
        except Exception as e:
            return f"❌ Unexpected error: {str(e)}"


# ============================================
# Convenience function for creating all tools
# ============================================

def create_zendfi_tools(
    api_key: Optional[str] = None,
    mode: str = "test",
    session_limit_usd: float = 10.0,
    user_wallet: Optional[str] = None,
    debug: bool = False,
) -> List[BaseTool]:
    """
    Create all ZendFi tools with shared configuration.
    
    Args:
        api_key: ZendFi API key (or set ZENDFI_API_KEY env var)
        mode: 'test' (devnet) or 'live' (mainnet)
        session_limit_usd: Default spending limit for auto-created sessions
        user_wallet: User's Solana wallet address (or set ZENDFI_USER_WALLET env var)
        debug: Enable debug logging
        
    Returns:
        List of configured ZendFi tools
        
    Example:
        >>> from langchain_zendfi import create_zendfi_tools
        >>> tools = create_zendfi_tools(session_limit_usd=25.0)
        >>> agent = create_agent(llm, tools)
    """
    common_config = {
        "api_key": api_key,
        "mode": mode,
        "debug": debug,
    }
    
    return [
        # Core payment tools
        ZendFiPaymentTool(**common_config, session_limit_usd=session_limit_usd),
        ZendFiBalanceTool(**common_config, session_limit_usd=session_limit_usd),
        
        # Session management
        ZendFiAgentSessionTool(**common_config, user_wallet=user_wallet),
        ZendFiCreateSessionTool(**common_config, user_wallet=user_wallet),
        
        # Discovery and pricing
        ZendFiMarketplaceTool(**common_config),
        ZendFiPricingTool(**common_config),
    ]


def create_minimal_zendfi_tools(
    api_key: Optional[str] = None,
    mode: str = "test",
    session_limit_usd: float = 10.0,
    debug: bool = False,
) -> List[BaseTool]:
    """
    Create minimal set of ZendFi tools (payment and balance only).
    
    Use this for simpler agents that only need payment capabilities.
    
    Args:
        api_key: ZendFi API key
        mode: 'test' or 'live'
        session_limit_usd: Default spending limit
        debug: Enable debug logging
        
    Returns:
        List with payment and balance tools only
    """
    common_config = {
        "api_key": api_key,
        "mode": mode,
        "debug": debug,
        "session_limit_usd": session_limit_usd,
    }
    
    return [
        ZendFiPaymentTool(**common_config),
        ZendFiBalanceTool(**common_config),
    ]
