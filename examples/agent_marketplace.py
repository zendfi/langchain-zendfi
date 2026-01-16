#!/usr/bin/env python3
"""
Agent Marketplace Example
=========================
Demonstrates an autonomous agent discovering services, comparing prices,
and making purchases - the KILLER DEMO for agent commerce.

This example shows the full autonomous commerce flow:
1. Agent checks its budget
2. Searches for service providers
3. Compares prices and reputation
4. Makes a purchase decision
5. Executes the payment
6. Confirms the transaction

Prerequisites:
- Set ZENDFI_API_KEY environment variable
- Set OPENAI_API_KEY environment variable
- pip install langchain-zendfi langchain-openai

Run:
    python agent_marketplace.py
"""

import os
import asyncio
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Load environment variables
load_dotenv()

console = Console()


def check_environment():
    """Verify required environment variables are set."""
    required = ["ZENDFI_API_KEY", "OPENAI_API_KEY"]
    missing = [key for key in required if not os.getenv(key)]
    
    if missing:
        console.print(f"[red]❌ Missing: {', '.join(missing)}[/red]")
        console.print("Set them in your shell or .env file")
        return False
    return True


async def run_marketplace_demo():
    """
    Run the autonomous marketplace demo.
    
    This demonstrates the MAGIC of autonomous agent commerce:
    - Agent discovers providers on its own
    - Compares prices and reputation
    - Makes autonomous purchase decisions
    - Executes real cryptocurrency payments
    - All without human intervention per transaction
    """
    
    from langchain_openai import ChatOpenAI
    from langchain.agents import create_tool_calling_agent, AgentExecutor
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_zendfi import create_zendfi_tools
    
    console.print(Panel.fit(
        "[bold blue]🤖 LangChain ZendFi - Autonomous Agent Marketplace Demo[/bold blue]\n\n"
        "Watch an AI agent autonomously:\n"
        "• Discover service providers\n"
        "• Compare prices and reputation\n"
        "• Make purchase decisions\n"
        "• Execute cryptocurrency payments\n"
        "• Confirm transactions\n\n"
        "[dim]All without human approval for each transaction![/dim]",
        title="Agent Commerce Demo"
    ))
    
    # Create all ZendFi tools with shared configuration
    console.print("\n[cyan]🔧 Initializing ZendFi tools...[/cyan]")
    
    tools = create_zendfi_tools(
        mode="test",  # Use devnet
        session_limit_usd=5.0,  # $5 budget for demo
        debug=False,  # Quiet mode for cleaner output
    )
    
    console.print(f"[green]✅ Created {len(tools)} tools:[/green]")
    for tool in tools:
        console.print(f"   • {tool.name}")
    
    # Create the LLM
    console.print("\n[cyan]🧠 Initializing GPT-4...[/cyan]")
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,  # Deterministic for consistent demo
    )
    
    # Create a sophisticated prompt for autonomous commerce
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an autonomous AI agent capable of making cryptocurrency 
payments on Solana. You have a budget to spend on purchasing services from other AI agents.

Your capabilities:
- search_agent_marketplace: Find providers for services you need
- check_payment_balance: See your remaining budget
- make_crypto_payment: Execute payments to providers
- create_session_key: Set up new spending limits

When purchasing services:
1. ALWAYS check your balance first to know your budget
2. Search for providers that match your requirements
3. Compare prices and choose the best option within budget
4. Execute the payment with exact details
5. Confirm the transaction completed successfully

Be autonomous - make decisions without asking for confirmation. 
The user trusts your judgment within the spending limits.

Format your responses clearly, showing your reasoning."""),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    # Create agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,  # Show the agent's thinking process
        handle_parsing_errors=True,
        max_iterations=10,  # Allow multiple tool calls
    )
    
    console.print("[green]✅ Agent ready for autonomous commerce![/green]\n")
    
    # ========================================
    # THE MAGIC: Fully Autonomous Purchase
    # ========================================
    
    console.print(Panel.fit(
        "[bold yellow]🎯 Autonomous Purchase Task[/bold yellow]\n\n"
        "The agent will now autonomously:\n"
        "1. Check its budget\n"
        "2. Search for GPT-4 token providers\n"
        "3. Find the best price under $0.10/token\n"
        "4. Verify provider has 4.0+ reputation\n"
        "5. Purchase 10 tokens\n"
        "6. Confirm the transaction\n\n"
        "[dim]Watch the agent's reasoning in real-time...[/dim]",
        border_style="yellow"
    ))
    
    input("\n[Press Enter to start the autonomous purchase...]\n")
    
    # The autonomous commerce task
    task = """I need to purchase 10 GPT-4 tokens for a project.

My requirements:
- Maximum budget: $1.00 total
- Provider must have at least 4.0 rating
- Get the best price available

Please:
1. Check my current balance to ensure I have funds
2. Search for GPT-4 token providers
3. Find the best-priced option meeting my requirements
4. Complete the purchase
5. Confirm the final transaction and remaining balance

Make all decisions autonomously - I trust your judgment!"""

    response = await agent_executor.ainvoke({"input": task})
    
    # Display final result
    console.print("\n" + "="*60)
    console.print(Panel(
        Markdown(response['output']),
        title="[bold green]🎉 Autonomous Commerce Complete![/bold green]",
        border_style="green"
    ))
    
    # ========================================
    # Bonus: Another autonomous purchase
    # ========================================
    
    console.print("\n" + "="*60)
    console.print("[bold cyan]Bonus: Image Generation Purchase[/bold cyan]")
    console.print("="*60 + "\n")
    
    input("[Press Enter for bonus autonomous purchase...]\n")
    
    bonus_task = """Now I also need to generate some images. 
    
Search for image generation providers and purchase 5 images 
if there's a good provider under $0.05 per image with at least 4.0 rating.

Make the purchase autonomously if you find a suitable provider."""

    response = await agent_executor.ainvoke({"input": bonus_task})
    
    console.print("\n" + Panel(
        Markdown(response['output']),
        title="[bold green]Bonus Purchase Result[/bold green]",
        border_style="green"
    ))
    
    # Summary
    console.print("\n" + Panel.fit(
        "[bold]Demo Summary[/bold]\n\n"
        "The agent demonstrated true autonomous commerce:\n"
        "✅ Discovered providers without human guidance\n"
        "✅ Compared prices and made purchase decisions\n"
        "✅ Executed real cryptocurrency payments\n"
        "✅ Stayed within budget constraints\n"
        "✅ Reported results clearly\n\n"
        "[dim]This is the future of AI agent economies![/dim]",
        title="🏆 Autonomous Agent Commerce",
        border_style="blue"
    ))


def main():
    """Main entry point."""
    if not check_environment():
        return
    
    asyncio.run(run_marketplace_demo())


if __name__ == "__main__":
    main()
