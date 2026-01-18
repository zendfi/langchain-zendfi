# Changelog

All notable changes to LangChain ZendFi will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-06-18

### Added

- **Device-Bound Session Keys**
  - `SessionKeysManager` - Complete session key lifecycle management
  - `DeviceBoundSessionKey` - Local keypair with delegation verification
  - Device-bound authentication with Ed25519 signing
  - Non-custodial by design - private keys never leave the device
  - Automatic delegation signature verification

- **Lit Protocol Integration**
  - End-to-end encryption of keypair secrets using Lit Protocol
  - Production microservice at `lit-service.zendfi.tech`
  - Network: `datil` (Lit mainnet)
  - Encrypted shards stored securely on-chain

- **Autonomous Agent Support**
  - `AutonomousAgentManager` - Stateful agent session management
  - Automated session refresh and token renewal
  - Payment execution with delegation verification
  - Spending limit enforcement (per-transaction, per-day)

- **Session Key API**
  - `create_session_key()` - Create new device-bound session key
  - `get_session_key()` - Retrieve existing session key
  - `list_session_keys()` - List all session keys for merchant
  - `revoke_session_key()` - Revoke session key access
  - `execute_delegated_payment()` - Execute payments using session key

- **Cryptographic Primitives**
  - `generate_keypair()` - Ed25519 keypair generation
  - `sign_message()` / `verify_signature()` - Cryptographic signing
  - `encrypt_keypair_with_lit()` - Lit Protocol encryption
  - PyNaCl-based signing for Solana compatibility

### Changed

- `ZendFiClient` now supports session key authentication mode
- `ZendFiPaymentTool` supports delegated payments via session keys
- Default Lit service URL updated to production

### Security

- Lit Protocol encryption adds additional layer of key protection
- Session keys are device-bound and non-transferable
- Delegation signatures prevent unauthorized key reuse
- Automatic session expiration enforcement

---

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
