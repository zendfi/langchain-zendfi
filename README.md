# LangChain ZendFi Integration

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/langchain-zendfi.svg)](https://badge.fury.io/py/langchain-zendfi)

**Enable LangChain agents to make autonomous cryptocurrency payments on Solana.**

LangChain ZendFi provides production-ready tools for AI agents to:
- **Make Payments**: Execute autonomous crypto payments within spending limits
- **Stay Secure**: Non-custodial session keys keep users in control
- **Go Gasless**: Backend handles all Solana transaction fees
- **Discover Services**: Search marketplace for agent service providers

## What's New in v0.2.0

- **🔐 Device-Bound Session Keys**: Ed25519 keypairs with delegation verification
- **🔒 Lit Protocol Encryption**: End-to-end encryption of keypair secrets
- **🤖 Autonomous Agent Manager**: Stateful session management with auto-refresh
- **⚡ Production Lit Service**: Deployed at `lit-service.zendfi.tech`

### Device-Bound Session Keys (Advanced)

For maximum security, create device-bound session keys with client-side cryptography:

```python
from langchain_zendfi import ZendFiClient
from langchain_zendfi.session_keys import SessionKeysManager, CreateSessionKeyOptions

# Initialize session key manager
client = ZendFiClient(mode="test")
manager = SessionKeysManager(client)

# Create device-bound session key with PIN encryption
result = await manager.create(CreateSessionKeyOptions(
    user_wallet="7xKNHuser...",
    agent_id="shopping-agent",
    limit_usdc=100.0,
    expires_hours=24,
    pin="123456",  # PIN-encrypts the private key
    enable_lit_protocol=True,  # Encrypt with Lit Protocol
))

print(f"Session Key ID: {result.session_key_id}")
print(f"Session Wallet: {result.session_wallet}")  # Public key

# Unlock to sign transactions
manager.unlock(result.session_key_id, pin="123456")

# Execute payment with delegation signature
payment = await manager.execute_payment(
    session_key_id=result.session_key_id,
    recipient="8xYZArecipient...",
    amount_usdc=1.50,
    description="AI service payment",
)
```

### Autonomous Agent Mode

Enable fully autonomous payments with spending attestations:

```python
from langchain_zendfi.autonomy import AutonomyManager, EnableAutonomyRequest

# Initialize autonomy manager
autonomy = AutonomyManager(client, manager)

# Enable autonomous mode with spending limits
delegate = await autonomy.enable(
    session_key_id=result.session_key_id,
    request=EnableAutonomyRequest(
        max_amount_usd=100.0,
        duration_hours=24,
    ),
)

print(f"Delegate ID: {delegate.delegate_id}")
print(f"Expires: {delegate.expires_at}")

# Execute autonomous payment (no human approval needed)
payment = await autonomy.execute_payment(
    delegate_id=delegate.delegate_id,
    recipient="8xYZArecipient...",
    amount_usdc=5.00,
    description="Autonomous purchase",
)

# Check autonomy status
status = await autonomy.get_status(delegate.delegate_id)
print(f"Remaining: ${status.remaining_amount_usd}")
print(f"Transactions: {status.transaction_count}")
```

### Cryptographic Utilities

Low-level crypto functions for advanced use cases:

```python
from langchain_zendfi.crypto import (
    generate_keypair,
    sign_message,
    encrypt_keypair_with_lit,
    verify_dependencies,
)

# Check crypto dependencies
deps = verify_dependencies()
print(f"PyNaCl: {deps['pynacl']}")
print(f"Cryptography: {deps['cryptography']}")

# Generate Ed25519 keypair
keypair = generate_keypair()
print(f"Public Key: {keypair.public_key}")  # Base58 encoded

# Sign a message
message = b"Payment attestation"
signature = sign_message(keypair, message)

# Encrypt keypair with Lit Protocol (production)
encrypted = encrypt_keypair_with_lit(
    keypair=keypair,
    access_control_conditions=[...],  # Lit ACCs
)
```

## Quick Start

### Installation

```bash
pip install langchain-zendfi
```

### Basic Usage

```python
from langchain_zendfi import ZendFiPaymentTool, ZendFiBalanceTool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_openai import ChatOpenAI

# Create payment tools with $10 spending limit
payment_tool = ZendFiPaymentTool(session_limit_usd=10.0)
balance_tool = ZendFiBalanceTool(session_limit_usd=10.0)

# Add to your LangChain agent
llm = ChatOpenAI(model="gpt-4o")
agent = create_tool_calling_agent(llm, [payment_tool, balance_tool], prompt)
executor = AgentExecutor(agent=agent, tools=[payment_tool, balance_tool])

# Agent can now make autonomous payments!
result = executor.invoke({
    "input": "Pay $0.50 to ProviderWallet123 for 5 GPT-4 tokens"
})
```

## Setup

### 1. Get API Key

Sign up at [zendfi.tech](https://zendfi.tech) to get your API key.

### 2. Set Environment Variables

```bash
export ZENDFI_API_KEY="zk_test_your_api_key"
export OPENAI_API_KEY="sk-your_openai_key"
```

Or create a `.env` file:

```env
ZENDFI_API_KEY=zk_test_your_api_key
OPENAI_API_KEY=sk-your_openai_key
```

## Available Tools

### `ZendFiPaymentTool`

Execute autonomous cryptocurrency payments.

```python
from langchain_zendfi import ZendFiPaymentTool

tool = ZendFiPaymentTool(
    mode="test",           # 'test' (devnet) or 'live' (mainnet)
    session_limit_usd=10.0 # Spending limit
)

# Direct invocation
result = tool.invoke({
    "recipient": "RecipientWallet123",
    "amount_usd": 1.50,
    "description": "15 GPT-4 tokens"
})
```

### `ZendFiBalanceTool`

Check session key balance and limits.

```python
from langchain_zendfi import ZendFiBalanceTool

tool = ZendFiBalanceTool()
result = tool.invoke({})
# Returns: remaining balance, spent amount, limit, expiration
```

### `ZendFiMarketplaceTool`

Search for service providers.

```python
from langchain_zendfi import ZendFiMarketplaceTool

tool = ZendFiMarketplaceTool()
result = tool.invoke({
    "service_type": "gpt4-tokens",
    "max_price": 0.10,
    "min_reputation": 4.0
})
# Returns: list of providers with prices and wallets
```

### `ZendFiCreateSessionTool`

Create a device-bound session key with custom limits.

```python
from langchain_zendfi import ZendFiCreateSessionTool

tool = ZendFiCreateSessionTool()
result = tool.invoke({
    "agent_id": "my-agent",
    "limit_usd": 25.0,
    "duration_days": 14
})
```

### `ZendFiAgentSessionTool` (Recommended)

Create an agent session with flexible spending limits. This is the **recommended** approach for LangChain agents - no client-side cryptography required.

```python
from langchain_zendfi import ZendFiAgentSessionTool

tool = ZendFiAgentSessionTool()
result = tool.invoke({
    "agent_id": "shopping-agent",
    "max_per_day": 100.0,
    "max_per_transaction": 25.0,
    "duration_hours": 24
})
```

### `ZendFiPricingTool`

Get PPP-adjusted pricing suggestions for fair global pricing.

```python
from langchain_zendfi import ZendFiPricingTool

tool = ZendFiPricingTool()
result = tool.invoke({
    "base_price": 10.0,
    "country_code": "BR"  # Brazil
})
# Returns: suggested price, adjustment factor, reasoning
```

### Create All Tools at Once

```python
from langchain_zendfi import create_zendfi_tools

tools = create_zendfi_tools(
    mode="test",
    session_limit_usd=10.0,
    debug=True
)
# Returns all 6 tools: Payment, Balance, AgentSession, 
#                      CreateSession, Marketplace, Pricing

# For simpler agents, use minimal tools:
from langchain_zendfi import create_minimal_zendfi_tools
tools = create_minimal_zendfi_tools(session_limit_usd=10.0)
# Returns: [PaymentTool, BalanceTool]
```

## Agent Commerce Example

Watch an agent autonomously discover providers and make purchases:

```python
from langchain_zendfi import create_zendfi_tools
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

# Setup
tools = create_zendfi_tools(session_limit_usd=5.0)
llm = ChatOpenAI(model="gpt-4o", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an autonomous AI agent that can make crypto payments.
    Always check your balance before making purchases.
    Make purchase decisions autonomously within your budget."""),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# The agent will autonomously:
# 1. Check budget
# 2. Search for providers
# 3. Compare prices
# 4. Make purchase decision
# 5. Execute payment
# 6. Confirm transaction

result = executor.invoke({
    "input": """I need to buy 10 GPT-4 tokens. 
    Find the cheapest provider with 4.0+ rating and complete the purchase.
    My budget is $1.00."""
})
```

## Security Architecture

LangChain ZendFi uses **session keys** for secure autonomous payments:

```
┌─────────────────────────────────────────────────────────────┐
│                    Session Key Flow                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. User creates session key with spending limit            │
│     └─ Keypair generated client-side (never exposed)        │
│     └─ Private key encrypted with PIN + Lit Protocol        │
│                                                             │
│  2. Agent makes payment request                             │
│     └─ Request validated against spending limits            │
│     └─ Delegation signature proves authorization            │
│                                                             │
│  3. Backend builds + submits transaction                    │
│     └─ Gasless: backend pays all Solana fees                │
│                                                             │
│  4. Payment confirmed on Solana (~400ms)                    │
│     └─ Transaction signature returned                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Security Features:**
- **Non-Custodial**: Private keys never leave user's device
- **Lit Protocol**: Keypair secrets encrypted with threshold cryptography
- **Spending Limits**: Hard caps on per-transaction and total spending
- **Time Bounds**: Session keys automatically expire
- **Delegation Signatures**: Cryptographic proof of authorization
- **Gasless**: No SOL required in session wallet
- **Audit Trail**: All transactions on-chain and verifiable

## Production vs Test Mode

| Feature | Test Mode (`mode="test"`) | Live Mode (`mode="live"`) |
|---------|---------------------------|---------------------------|
| Network | Solana Devnet | Solana Mainnet |
| Tokens | Test USDC | Real USDC |
| API Key | `zk_test_...` | `zk_live_...` |
| Suitable for | Development, demos | Production apps |

## Examples

### Basic Payment

```bash
cd examples
python basic_payment.py
```

### Agent Marketplace Demo

```bash
cd examples
python agent_marketplace.py
```

### Jupyter Notebook

```bash
jupyter notebook examples/notebooks/getting_started.ipynb
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=langchain_zendfi
```

## API Reference

### ZendFiClient

Direct API access without LangChain:

```python
from langchain_zendfi import ZendFiClient, SessionLimits

client = ZendFiClient(
    api_key="zk_test_...",
    mode="test",
)

# Recommended: Create agent session (no client-side crypto needed)
session = await client.create_agent_session(
    agent_id="my-agent",
    user_wallet="7xKNH...",
    limits=SessionLimits(
        max_per_day=100.0,
        max_per_transaction=25.0,
    ),
)
print(f"Session: {session.id}")

# Make smart payment
payment = await client.smart_payment(
    agent_id="my-agent",
    user_wallet="8xYZA...",
    amount_usd=1.50,
    description="Service payment",
    session_token=session.session_token,
)
print(f"Signature: {payment.transaction_signature}")

# Get PPP pricing
ppp = await client.get_ppp_factor("BR")  # Brazil
print(f"Adjustment: {ppp.adjustment_percentage}%")

# Check session key status
status = await client.get_session_status()
print(f"Remaining: ${status.remaining_usdc}")
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Clone the repo
git clone https://github.com/zendfi/langchain-zendfi.git
cd langchain-zendfi

# Install in dev mode
pip install -e ".[dev]"

# Run tests before submitting PR
pytest
```

## License

MIT License - see [LICENSE](LICENSE)

## Support

- **Documentation**: [docs.zendfi.tech](https://docs.zendfi.tech)
- **Discord**: [discord.gg/zendfi](https://discord.gg/zendfi)
- **Email**: support@zendfi.tech
- **Issues**: [GitHub Issues](https://github.com/zendfi/langchain-zendfi/issues)

---

Built with ❤️ by the [ZendFi](https://zendfi.tech) team
