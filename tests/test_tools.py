"""
Unit Tests for LangChain ZendFi Tools
=====================================
Tests tool initialization, schemas, and output formatting.
Uses mocked API responses matching the real ZendFi API structure.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_zendfi import (
    ZendFiPaymentTool,
    ZendFiMarketplaceTool,
    ZendFiBalanceTool,
    ZendFiCreateSessionTool,
    ZendFiAgentSessionTool,
    ZendFiPricingTool,
    create_zendfi_tools,
    create_minimal_zendfi_tools,
)
from langchain_zendfi.client import (
    ZendFiClient,
    PaymentResult,
    SmartPaymentResult,
    SessionKeyStatus,
    SessionKeyResult,
    AgentSession,
    SessionLimits,
    AgentProvider,
    PPPFactor,
    PricingSuggestion,
)


class TestToolInitialization:
    """Test that tools initialize correctly."""
    
    def test_payment_tool_has_correct_name(self):
        """Payment tool should have the expected name."""
        tool = ZendFiPaymentTool(api_key="test_key")
        assert tool.name == "make_crypto_payment"
    
    def test_marketplace_tool_has_correct_name(self):
        """Marketplace tool should have the expected name."""
        tool = ZendFiMarketplaceTool(api_key="test_key")
        assert tool.name == "search_agent_marketplace"
    
    def test_balance_tool_has_correct_name(self):
        """Balance tool should have the expected name."""
        tool = ZendFiBalanceTool(api_key="test_key")
        assert tool.name == "check_payment_balance"
    
    def test_create_session_tool_has_correct_name(self):
        """Create session tool should have the expected name."""
        tool = ZendFiCreateSessionTool(api_key="test_key")
        assert tool.name == "create_session_key"
    
    def test_agent_session_tool_has_correct_name(self):
        """Agent session tool should have the expected name."""
        tool = ZendFiAgentSessionTool(api_key="test_key")
        assert tool.name == "create_agent_session"
    
    def test_pricing_tool_has_correct_name(self):
        """Pricing tool should have the expected name."""
        tool = ZendFiPricingTool(api_key="test_key")
        assert tool.name == "get_pricing_suggestion"
    
    def test_tools_have_descriptions(self):
        """All tools should have non-empty descriptions."""
        tools = create_zendfi_tools(api_key="test_key")
        for tool in tools:
            assert tool.description
            assert len(tool.description) > 50
    
    def test_create_zendfi_tools_returns_six_tools(self):
        """create_zendfi_tools should return all six tools."""
        tools = create_zendfi_tools(api_key="test_key")
        assert len(tools) == 6
        
        names = {tool.name for tool in tools}
        assert "make_crypto_payment" in names
        assert "search_agent_marketplace" in names
        assert "check_payment_balance" in names
        assert "create_session_key" in names
        assert "create_agent_session" in names
        assert "get_pricing_suggestion" in names
    
    def test_create_minimal_tools_returns_two_tools(self):
        """create_minimal_zendfi_tools should return payment and balance tools."""
        tools = create_minimal_zendfi_tools(api_key="test_key")
        assert len(tools) == 2
        
        names = {tool.name for tool in tools}
        assert "make_crypto_payment" in names
        assert "check_payment_balance" in names


class TestPaymentToolSchema:
    """Test payment tool input schema."""
    
    def test_payment_tool_has_args_schema(self):
        """Payment tool should have an args schema."""
        tool = ZendFiPaymentTool(api_key="test_key")
        assert tool.args_schema is not None
    
    def test_payment_schema_requires_recipient(self):
        """Payment schema should require recipient field."""
        tool = ZendFiPaymentTool(api_key="test_key")
        schema = tool.args_schema.model_json_schema()
        assert "recipient" in schema["properties"]
        assert "recipient" in schema["required"]
    
    def test_payment_schema_requires_amount(self):
        """Payment schema should require amount_usd field."""
        tool = ZendFiPaymentTool(api_key="test_key")
        schema = tool.args_schema.model_json_schema()
        assert "amount_usd" in schema["properties"]
        assert "amount_usd" in schema["required"]
    
    def test_payment_schema_requires_description(self):
        """Payment schema should require description field."""
        tool = ZendFiPaymentTool(api_key="test_key")
        schema = tool.args_schema.model_json_schema()
        assert "description" in schema["properties"]
        assert "description" in schema["required"]


class TestMarketplaceToolSchema:
    """Test marketplace tool input schema."""
    
    def test_marketplace_tool_has_args_schema(self):
        """Marketplace tool should have an args schema."""
        tool = ZendFiMarketplaceTool(api_key="test_key")
        assert tool.args_schema is not None
    
    def test_marketplace_schema_requires_service_type(self):
        """Marketplace schema should require service_type."""
        tool = ZendFiMarketplaceTool(api_key="test_key")
        schema = tool.args_schema.model_json_schema()
        assert "service_type" in schema["properties"]
        assert "service_type" in schema["required"]
    
    def test_marketplace_schema_has_optional_max_price(self):
        """Marketplace schema should have optional max_price."""
        tool = ZendFiMarketplaceTool(api_key="test_key")
        schema = tool.args_schema.model_json_schema()
        assert "max_price" in schema["properties"]
        # max_price should NOT be required
        assert "max_price" not in schema.get("required", [])


class TestBalanceToolSchema:
    """Test balance tool input schema."""
    
    def test_balance_tool_has_args_schema(self):
        """Balance tool should have an args schema (even if empty)."""
        tool = ZendFiBalanceTool(api_key="test_key")
        assert tool.args_schema is not None
    
    def test_balance_schema_has_no_required_fields(self):
        """Balance schema should not require any fields."""
        tool = ZendFiBalanceTool(api_key="test_key")
        schema = tool.args_schema.model_json_schema()
        required = schema.get("required", [])
        assert len(required) == 0


class TestPaymentToolExecution:
    """Test payment tool execution with mocked client."""
    
    @pytest.mark.asyncio
    async def test_successful_payment_returns_confirmation(self):
        """Successful payment should return confirmation message."""
        tool = ZendFiPaymentTool(api_key="test_key")
        
        # Mock the client with SmartPaymentResult (production API)
        mock_client = AsyncMock()
        mock_client._session_agent_id = "test-agent"
        mock_client.smart_payment.return_value = SmartPaymentResult(
            payment_id="pay_123",
            status="confirmed",
            amount_usd=1.50,
            gasless_used=True,
            settlement_complete=True,
            receipt_url="https://api.zendfi.com/receipt/pay_123",
            next_steps="",
            created_at="2024-01-16T00:00:00Z",
            transaction_signature="5wHuFakeSignature12345678901234567890",
            confirmed_in_ms=450,
        )
        tool._client = mock_client
        
        result = await tool._arun(
            recipient="TestWallet123",
            amount_usd=1.50,
            description="Test payment",
        )
        
        assert "successful" in result.lower() or "✅" in result
        assert "$1.50" in result
        assert "TestWallet123" in result
    
    @pytest.mark.asyncio
    async def test_payment_formats_amount_correctly(self):
        """Payment confirmation should format amounts with 2 decimal places."""
        tool = ZendFiPaymentTool(api_key="test_key")
        
        mock_client = AsyncMock()
        mock_client._session_agent_id = "test-agent"
        mock_client.smart_payment.return_value = SmartPaymentResult(
            payment_id="pay_123",
            status="confirmed",
            amount_usd=10.00,
            gasless_used=False,
            settlement_complete=True,
            receipt_url="",
            next_steps="",
            created_at="2024-01-16T00:00:00Z",
            transaction_signature="5wHuFakeSignature",
        )
        tool._client = mock_client
        
        result = await tool._arun(
            recipient="Wallet123",
            amount_usd=10.00,
            description="Test",
        )
        
        # Should show $10.00, not $10.0 or $10
        assert "$10.00" in result
    
    @pytest.mark.asyncio
    async def test_payment_shows_gasless_indicator(self):
        """Payment should indicate when gasless was used."""
        tool = ZendFiPaymentTool(api_key="test_key")
        
        mock_client = AsyncMock()
        mock_client._session_agent_id = "test-agent"
        mock_client.smart_payment.return_value = SmartPaymentResult(
            payment_id="pay_123",
            status="confirmed",
            amount_usd=5.00,
            gasless_used=True,
            settlement_complete=True,
            receipt_url="",
            next_steps="",
            created_at="2024-01-16T00:00:00Z",
            transaction_signature="5wHuFakeSignature",
        )
        tool._client = mock_client
        
        result = await tool._arun(
            recipient="Wallet123",
            amount_usd=5.00,
            description="Test",
        )
        
        assert "gasless" in result.lower() or "🎁" in result


class TestMarketplaceToolExecution:
    """Test marketplace tool execution with mocked client."""
    
    @pytest.mark.asyncio
    async def test_search_returns_formatted_providers(self):
        """Marketplace search should return formatted provider list."""
        tool = ZendFiMarketplaceTool(api_key="test_key")
        
        mock_client = AsyncMock()
        mock_client.search_marketplace.return_value = [
            AgentProvider(
                agent_id="provider-1",
                agent_name="Test Provider",
                service_type="gpt4-tokens",
                price_per_unit=0.10,
                wallet="ProviderWallet123",
                reputation=4.5,
            ),
        ]
        tool._client = mock_client
        
        result = await tool._arun(
            service_type="gpt4-tokens",
            max_price=0.15,
            min_reputation=4.0,
        )
        
        assert "Test Provider" in result
        assert "0.10" in result or "$0.100" in result
        assert "4.5" in result
        assert "ProviderWallet123" in result
    
    @pytest.mark.asyncio
    async def test_empty_search_returns_helpful_message(self):
        """Empty search results should return helpful message."""
        tool = ZendFiMarketplaceTool(api_key="test_key")
        
        mock_client = AsyncMock()
        mock_client.search_marketplace.return_value = []
        tool._client = mock_client
        
        result = await tool._arun(
            service_type="nonexistent-service",
        )
        
        assert "no provider" in result.lower() or "not found" in result.lower()


class TestBalanceToolExecution:
    """Test balance tool execution with mocked client."""
    
    @pytest.mark.asyncio
    async def test_balance_returns_status_info(self):
        """Balance check should return status information."""
        tool = ZendFiBalanceTool(api_key="test_key")
        
        mock_client = AsyncMock()
        mock_client.get_session_status.return_value = SessionKeyStatus(
            session_key_id="session_123",
            is_active=True,
            is_approved=True,
            limit_usdc=10.0,
            used_amount_usdc=2.50,
            remaining_usdc=7.50,
            expires_at="2026-01-23T00:00:00Z",
            days_until_expiry=7,
        )
        tool._client = mock_client
        
        result = await tool._arun()
        
        assert "$7.50" in result or "7.50" in result
        assert "Active" in result or "active" in result or "🟢" in result


class TestClientIntegration:
    """Test ZendFi client functionality."""
    
    def test_client_requires_api_key(self):
        """Client should require API key."""
        # Clear env var if set
        import os
        old_key = os.environ.pop("ZENDFI_API_KEY", None)
        
        try:
            with pytest.raises(ValueError) as exc_info:
                ZendFiClient()
            assert "API key required" in str(exc_info.value)
        finally:
            if old_key:
                os.environ["ZENDFI_API_KEY"] = old_key
    
    def test_client_accepts_api_key_parameter(self):
        """Client should accept API key as parameter."""
        client = ZendFiClient(api_key="test_key_123")
        assert client.api_key == "test_key_123"
    
    def test_client_defaults_to_test_mode(self):
        """Client should default to test mode."""
        client = ZendFiClient(api_key="test_key")
        assert client.mode.value == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
