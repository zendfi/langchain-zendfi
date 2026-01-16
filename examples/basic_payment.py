#!/usr/bin/env python3
"""
Basic Payment Example
=====================
Demonstrates how to give a LangChain agent the ability to make 
autonomous cryptocurrency payments on Solana.

This example shows:
1. Creating payment and balance tools
2. Initializing an agent with these tools
3. Making a simple payment
4. Checking the resulting balance

Prerequisites:
- Set ZENDFI_API_KEY environment variable
- Set OPENAI_API_KEY environment variable (for GPT-4)
- pip install langchain-zendfi langchain-openai

Run:
    python basic_payment.py
"""

import os
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def check_environment():
    """Verify required environment variables are set."""
    required = {
        "ZENDFI_API_KEY": "Your ZendFi API key (get from zendfi.com)",
        "OPENAI_API_KEY": "Your OpenAI API key (for GPT-4)",
    }
    
    missing = []
    for key, description in required.items():
        if not os.getenv(key):
            missing.append(f"  - {key}: {description}")
    
    if missing:
        print("❌ Missing required environment variables:\n")
        print("\n".join(missing))
        print("\nSet them in your shell or create a .env file.")
        return False
    
    print("✅ Environment configured correctly")
    return True


async def run_basic_payment_demo():
    """Run the basic payment demonstration."""
    
    from langchain_openai import ChatOpenAI
    from langchain.agents import create_tool_calling_agent, AgentExecutor
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_zendfi import ZendFiPaymentTool, ZendFiBalanceTool
    
    print("\n" + "="*60)
    print("LangChain ZendFi - Basic Payment Demo")
    print("="*60 + "\n")
    
    # Initialize tools with configuration
    # The session key will be auto-created with a $10 limit
    print("🔧 Initializing ZendFi tools...")
    
    payment_tool = ZendFiPaymentTool(
        mode="test",  # Use devnet for testing
        session_limit_usd=10.0,  # $10 spending limit
        debug=True,  # Enable logging for demo
    )
    
    balance_tool = ZendFiBalanceTool(
        mode="test",
        session_limit_usd=10.0,
        debug=True,
    )
    
    tools = [payment_tool, balance_tool]
    print(f"✅ Created {len(tools)} tools: {[t.name for t in tools]}\n")
    
    # Create the LLM
    print("🤖 Initializing GPT-4...")
    llm = ChatOpenAI(
        model="gpt-4o",  # or "gpt-4-turbo" for faster responses
        temperature=0,  # Deterministic for payments
    )
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful AI assistant with the ability to make 
cryptocurrency payments on Solana. You can check your payment balance and 
make payments to other wallets.

When asked to make a payment:
1. First check your balance to ensure you have sufficient funds
2. Make the payment to the specified recipient
3. Confirm the transaction was successful

Always be helpful and explain what you're doing."""),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    # Create agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,  # Show agent's thinking
        handle_parsing_errors=True,
    )
    
    print("✅ Agent created and ready!\n")
    
    # ========================================
    # Example 1: Check Balance
    # ========================================
    print("="*60)
    print("Example 1: Check Payment Balance")
    print("="*60 + "\n")
    
    response = await agent_executor.ainvoke({
        "input": "What's my current payment balance?"
    })
    print(f"\n📋 Agent Response:\n{response['output']}\n")
    
    # ========================================
    # Example 2: Make a Payment
    # ========================================
    print("="*60)
    print("Example 2: Make a Payment")
    print("="*60 + "\n")
    
    response = await agent_executor.ainvoke({
        "input": """Please send $0.50 to wallet address 'AlphaProvider1234567890abcdef' 
for purchasing 5 GPT-4 tokens."""
    })
    print(f"\n📋 Agent Response:\n{response['output']}\n")
    
    # ========================================
    # Example 3: Check Balance After Payment
    # ========================================
    print("="*60)
    print("Example 3: Verify Balance After Payment")
    print("="*60 + "\n")
    
    response = await agent_executor.ainvoke({
        "input": "Check my balance again to see how much was spent."
    })
    print(f"\n📋 Agent Response:\n{response['output']}\n")
    
    print("="*60)
    print("Demo Complete!")
    print("="*60)


def main():
    """Main entry point."""
    if not check_environment():
        return
    
    # Run the async demo
    asyncio.run(run_basic_payment_demo())


if __name__ == "__main__":
    main()
