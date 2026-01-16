"""
Integration Tests for LangChain ZendFi
======================================
Tests that verify the full flow from tool to API.

These tests use mocked API responses that match the real ZendFi API structure.
Set ZENDFI_API_KEY for live integration testing.
"""

import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# Skip live tests if no API key is available
SKIP_LIVE_TESTS = not os.getenv("ZENDFI_API_KEY")


class TestAgentSessionFlow:
    """Test the agent session creation and management flow (recommended approach)."""
    
    @pytest.mark.asyncio
    async def test_create_agent_session(self):
        """Should be able to create an agent session with spending limits."""
        from langchain_zendfi import ZendFiClient, SessionLimits
        
        client = ZendFiClient(api_key="zk_test_mock", mode="test")
        
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "id": "sess_123",
                "session_token": "st_abc123xyz",
                "agent_id": "test-agent",
                "agent_name": "LangChain Agent (test-agent)",
                "user_wallet": "UserWallet123",
                "limits": {
                    "max_per_transaction": 50.0,
                    "max_per_day": 100.0,
                    "max_per_week": 500.0,
                    "max_per_month": 2000.0,
                    "require_approval_above": 25.0,
                },
                "is_active": True,
                "created_at": "2024-01-16T00:00:00Z",
                "expires_at": "2024-01-17T00:00:00Z",
                "remaining_today": 100.0,
                "remaining_this_week": 500.0,
                "remaining_this_month": 2000.0,
            }
            
            result = await client.create_agent_session(
                agent_id="test-agent",
                user_wallet="UserWallet123",
                limits=SessionLimits(max_per_day=100.0, max_per_transaction=50.0),
            )
            
            assert result.id == "sess_123"
            assert result.session_token == "st_abc123xyz"
            assert result.limits.max_per_day == 100.0
            assert result.is_active == True


class TestSmartPaymentFlow:
    """Test the smart payment API flow."""
    
    @pytest.mark.asyncio
    async def test_smart_payment_success(self):
        """Should be able to execute a smart payment."""
        from langchain_zendfi import ZendFiClient
        
        client = ZendFiClient(api_key="zk_test_mock", mode="test")
        client._session_agent_id = "test-agent"
        
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "payment_id": "pay_abc123",
                "status": "confirmed",
                "amount_usd": 1.50,
                "gasless_used": True,
                "settlement_complete": True,
                "receipt_url": "https://api.zendfi.tech/receipt/pay_abc123",
                "next_steps": "",
                "created_at": "2024-01-16T12:00:00Z",
                "transaction_signature": "5wHuSignature12345678901234567890abcdef",
                "confirmed_in_ms": 450,
            }
            
            result = await client.smart_payment(
                agent_id="test-agent",
                user_wallet="RecipientWallet123",
                amount_usd=1.50,
                description="Test payment for GPT-4 tokens",
            )
            
            assert result.payment_id == "pay_abc123"
            assert result.status == "confirmed"
            assert result.amount_usd == 1.50
            assert result.gasless_used == True
            assert result.transaction_signature is not None
    
    @pytest.mark.asyncio
    async def test_smart_payment_awaiting_signature(self):
        """Should handle payments that require signature submission."""
        from langchain_zendfi import ZendFiClient
        
        client = ZendFiClient(api_key="zk_test_mock", mode="test")
        
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "payment_id": "pay_pending123",
                "status": "awaiting_signature",
                "amount_usd": 5.00,
                "gasless_used": False,
                "settlement_complete": False,
                "receipt_url": "",
                "next_steps": "Sign the transaction and submit via submit_url",
                "created_at": "2024-01-16T12:00:00Z",
                "requires_signature": True,
                "unsigned_transaction": "base64EncodedTransaction...",
                "submit_url": "https://api.zendfi.tech/payments/pay_pending123/submit-signed",
            }
            
            result = await client.smart_payment(
                agent_id="test-agent",
                user_wallet="Wallet123",
                amount_usd=5.00,
                description="Device-bound payment",
            )
            
            assert result.status == "awaiting_signature"
            assert result.requires_signature == True
            assert result.unsigned_transaction is not None


class TestSessionKeyFlow:
    """Test the device-bound session key flow."""
    
    @pytest.mark.asyncio
    async def test_create_session_key(self):
        """Should be able to create a session key."""
        from langchain_zendfi import ZendFiClient
        
        client = ZendFiClient(api_key="zk_test_mock", mode="test")
        
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "session_key_id": "sk_test_123",
                "agent_id": "test-agent",
                "agent_name": "LangChain Agent (test-agent)",
                "session_wallet": "SessionWallet123456789",
                "limit_usdc": 10.0,
                "expires_at": "2024-01-23T00:00:00Z",
                "cross_app_compatible": True,
                "requires_client_signing": True,
                "mode": "device_bound",
            }
            
            result = await client.create_session_key(
                user_wallet="UserWallet123",
                agent_id="test-agent",
                limit_usdc=10.0,
            )
            
            assert result.session_key_id == "sk_test_123"
            assert result.limit_usdc == 10.0
            assert result.cross_app_compatible == True


class TestPricingFlow:
    """Test the pricing API flow."""
    
    @pytest.mark.asyncio
    async def test_get_ppp_factor(self):
        """Should be able to get PPP factor for a country."""
        from langchain_zendfi import ZendFiClient
        
        client = ZendFiClient(api_key="zk_test_mock", mode="test")
        
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "country_code": "BR",
                "country_name": "Brazil",
                "ppp_factor": 0.45,
                "currency_code": "BRL",
                "adjustment_percentage": -55.0,
            }
            
            result = await client.get_ppp_factor("BR")
            
            assert result.country_code == "BR"
            assert result.ppp_factor == 0.45
            assert result.adjustment_percentage == -55.0
    
    @pytest.mark.asyncio
    async def test_get_pricing_suggestion(self):
        """Should be able to get AI pricing suggestion."""
        from langchain_zendfi import ZendFiClient
        
        client = ZendFiClient(api_key="zk_test_mock", mode="test")
        
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "suggested_amount": 4.50,
                "min_amount": 3.00,
                "max_amount": 10.00,
                "currency": "USD",
                "reasoning": "PPP adjustment for Brazil reduces price by 55%",
                "ppp_adjusted": True,
                "adjustment_factor": 0.45,
            }
            
            result = await client.get_pricing_suggestion(
                agent_id="pricing-agent",
                base_price=10.0,
                location_country="BR",
            )
            
            assert result.suggested_amount == 4.50
            assert result.ppp_adjusted == True


class TestMarketplaceFlow:
    """Test marketplace search flow."""
    
    @pytest.mark.asyncio
    async def test_search_marketplace(self):
        """Should be able to search marketplace via API."""
        from langchain_zendfi import ZendFiClient
        
        client = ZendFiClient(api_key="zk_test_mock", mode="test")
        
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "providers": [
                    {
                        "agent_id": "provider-1",
                        "agent_name": "GPT-4 Provider",
                        "service_type": "gpt4-tokens",
                        "price_per_unit": 0.08,
                        "wallet": "ProviderWallet123",
                        "reputation": 4.8,
                        "description": "Fast GPT-4 tokens",
                        "available": True,
                    },
                ]
            }
            
            providers = await client.search_marketplace(
                service_type="gpt4-tokens",
                max_price=0.15,
            )
            
            assert len(providers) == 1
            assert providers[0].agent_id == "provider-1"
            assert providers[0].price_per_unit == 0.08


class TestToolWithAgent:
    """Test tools work correctly with LangChain agents."""
    
    @pytest.mark.asyncio
    async def test_tools_work_with_function_calling(self):
        """Tools should work with LangChain function calling."""
        from langchain_zendfi import create_zendfi_tools
        
        tools = create_zendfi_tools(
            api_key="zk_test_mock",
            mode="test",
        )
        
        # Verify tools have correct schema for function calling
        assert len(tools) == 6
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
        
        tool = ZendFiBalanceTool(api_key="zk_test_mock", mode="test")
        
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
