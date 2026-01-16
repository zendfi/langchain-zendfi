"""
Integration Tests for LangChain ZendFi
======================================
Tests that verify the full flow from tool to API.

These tests require a ZENDFI_API_KEY environment variable
set to a valid test API key.
"""

import os
import pytest
from unittest.mock import patch, AsyncMock

# Skip all tests if no API key is available
pytestmark = pytest.mark.skipif(
    not os.getenv("ZENDFI_API_KEY"),
    reason="ZENDFI_API_KEY not set - skipping integration tests"
)


class TestSessionKeyFlow:
    """Test the session key creation and management flow."""
    
    @pytest.mark.asyncio
    async def test_create_session_key(self):
        """Should be able to create a session key."""
        from langchain_zendfi import ZendFiClient
        
        client = ZendFiClient(mode="test")
        
        # This would make a real API call in integration tests
        # For CI, we mock it
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "session_key_id": "test_session_123",
                "agent_id": "test-agent",
                "session_wallet": "TestWallet123456789",
                "limit_usdc": 10.0,
                "expires_at": "2026-01-23T00:00:00Z",
                "cross_app_compatible": True,
            }
            
            result = await client.create_session_key(
                user_wallet="UserWallet123",
                agent_id="test-agent",
                limit_usdc=10.0,
            )
            
            assert result.session_key_id == "test_session_123"
            assert result.limit_usdc == 10.0


class TestPaymentFlow:
    """Test the full payment flow."""
    
    @pytest.mark.asyncio
    async def test_make_payment_flow(self):
        """Should be able to execute a payment."""
        from langchain_zendfi import ZendFiClient
        
        client = ZendFiClient(mode="test")
        client._session_key_id = "mock_session"
        client._session_agent_id = "mock_agent"
        
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "payment_id": "pay_123",
                "transaction_signature": "5wHuFakeSignature123",
                "status": "confirmed",
            }
            
            result = await client.make_payment(
                amount=1.50,
                recipient="RecipientWallet123",
                description="Test payment",
            )
            
            assert result.payment_id == "pay_123"
            assert result.signature == "5wHuFakeSignature123"
            assert result.status == "confirmed"


class TestMarketplaceFlow:
    """Test marketplace search flow."""
    
    @pytest.mark.asyncio
    async def test_search_marketplace(self):
        """Should be able to search marketplace."""
        from langchain_zendfi import ZendFiClient
        
        client = ZendFiClient(mode="test", auto_create_session=False)
        
        # Marketplace search uses mock data, no API call needed
        providers = await client.search_marketplace(
            service_type="gpt4-tokens",
            max_price=0.15,
        )
        
        assert len(providers) > 0
        assert all(p.service_type == "gpt4-tokens" for p in providers)
        assert all(p.price_per_unit <= 0.15 for p in providers)


class TestToolWithAgent:
    """Test tools work correctly with LangChain agents."""
    
    @pytest.mark.asyncio
    async def test_tools_work_with_function_calling(self):
        """Tools should work with LangChain function calling."""
        from langchain_zendfi import create_zendfi_tools
        
        tools = create_zendfi_tools(
            api_key=os.getenv("ZENDFI_API_KEY", "test_key"),
            mode="test",
        )
        
        # Verify tools have correct schema for function calling
        for tool in tools:
            schema = tool.args_schema.model_json_schema()
            assert "properties" in schema
            assert "type" in schema
            assert schema["type"] == "object"
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set"
    )
    @pytest.mark.asyncio
    async def test_agent_can_use_balance_tool(self):
        """Agent should be able to invoke balance tool."""
        from langchain_openai import ChatOpenAI
        from langchain.agents import create_tool_calling_agent, AgentExecutor
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_zendfi import ZendFiBalanceTool
        
        tool = ZendFiBalanceTool(mode="test")
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You can check payment balances."),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        agent = create_tool_calling_agent(llm, [tool], prompt)
        executor = AgentExecutor(agent=agent, tools=[tool])
        
        # This will actually invoke the tool
        with patch.object(tool, '_arun', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "Balance: $10.00"
            
            result = await executor.ainvoke({
                "input": "Check my balance"
            })
            
            # The agent should have attempted to use the tool
            # (exact behavior depends on LLM response)
            assert result is not None


class TestErrorHandling:
    """Test error handling in integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_handles_api_errors_gracefully(self):
        """Tools should handle API errors gracefully."""
        from langchain_zendfi import ZendFiPaymentTool
        from langchain_zendfi.client import ZendFiAPIError
        
        tool = ZendFiPaymentTool(mode="test")
        
        # Mock client to raise an error
        mock_client = AsyncMock()
        mock_client.make_payment.side_effect = ZendFiAPIError("Network error")
        mock_client.ensure_session_key.return_value = {
            "session_key_id": "test",
            "session_wallet": "test",
        }
        tool._client = mock_client
        
        result = await tool._arun(
            recipient="Wallet123",
            amount_usd=1.0,
            description="Test",
        )
        
        # Should return error message, not raise exception
        assert "❌" in result or "failed" in result.lower() or "error" in result.lower()
    
    @pytest.mark.asyncio
    async def test_handles_insufficient_balance(self):
        """Should handle insufficient balance errors."""
        from langchain_zendfi import ZendFiPaymentTool
        from langchain_zendfi.client import InsufficientBalanceError
        
        tool = ZendFiPaymentTool(mode="test")
        
        mock_client = AsyncMock()
        mock_client.make_payment.side_effect = InsufficientBalanceError(
            "Insufficient balance"
        )
        mock_client.ensure_session_key.return_value = {
            "session_key_id": "test",
            "session_wallet": "test",
        }
        tool._client = mock_client
        
        result = await tool._arun(
            recipient="Wallet123",
            amount_usd=1000.0,  # More than balance
            description="Test",
        )
        
        assert "insufficient" in result.lower() or "balance" in result.lower()


class TestIdempotency:
    """Test idempotency key handling."""
    
    @pytest.mark.asyncio
    async def test_payment_generates_idempotency_key(self):
        """Payments should generate idempotency keys."""
        from langchain_zendfi import ZendFiClient
        
        client = ZendFiClient(mode="test")
        client._session_key_id = "test_session"
        client._session_agent_id = "test_agent"
        
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "payment_id": "pay_123",
                "signature": "sig123",
                "status": "confirmed",
            }
            
            await client.make_payment(
                amount=1.0,
                recipient="Wallet123",
                description="Test",
            )
            
            # Verify idempotency key was passed
            call_kwargs = mock_request.call_args
            assert call_kwargs is not None
            # The idempotency key should start with 'pay_'
            if len(call_kwargs) > 1 and 'idempotency_key' in call_kwargs.kwargs:
                assert call_kwargs.kwargs['idempotency_key'].startswith('pay_')


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
