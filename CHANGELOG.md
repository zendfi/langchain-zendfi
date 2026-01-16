# Changelog

All notable changes to LangChain ZendFi will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-16

### Added

- **Core Tools**
  - `ZendFiPaymentTool` - Execute autonomous cryptocurrency payments on Solana
  - `ZendFiBalanceTool` - Check session key balance and spending limits
  - `ZendFiMarketplaceTool` - Search for agent service providers
  - `ZendFiCreateSessionTool` - Create device-bound session keys
  - `ZendFiAgentSessionTool` - Create agent sessions with flexible limits (recommended)
  - `ZendFiPricingTool` - Get PPP-adjusted pricing suggestions

- **Factory Functions**
  - `create_zendfi_tools()` - Create all 6 tools with shared configuration
  - `create_minimal_zendfi_tools()` - Create just payment and balance tools

- **Client API**
  - `ZendFiClient` - Direct HTTP client for ZendFi API
  - Agent Sessions API (recommended for LangChain)
  - Smart Payments API with gasless transactions
  - Session Keys API for device-bound keys
  - Pricing API with PPP support
  - Marketplace API for provider discovery

- **Error Handling**
  - `ZendFiAPIError` - Base API error
  - `AuthenticationError` - Invalid API key
  - `InsufficientBalanceError` - Not enough funds
  - `SessionKeyExpiredError` - Session expired
  - `RateLimitError` - Rate limit exceeded
  - `ValidationError` - Request validation failed

- **Examples**
  - Basic payment example with GPT-4
  - Agent marketplace demo with autonomous purchasing
  - Jupyter notebook tutorial

- **Documentation**
  - Comprehensive README with quick start guide
  - API reference documentation
  - Contributing guidelines

### Security

- Non-custodial session keys - private keys never leave user's device
- Spending limits enforced server-side
- Idempotency keys prevent duplicate payments
- Session keys auto-expire

---

## [Unreleased]

### Planned
- Webhook support for payment notifications
- Multi-chain support (Ethereum, Base)
- Agent-to-agent direct payments
- Subscription/recurring payments
