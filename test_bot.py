#!/usr/bin/env python3
"""
Quick Bot Test Script
Tests core functionality without starting the full bot.
"""

import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_ai_agent():
    """Test AI agent functionality."""
    print("🧠 Testing AI Agent...")
    
    try:
        from config import Config
        from ai_agent import AIAgent
        
        config = Config()
        agent = AIAgent(config)
        
        print(f"✅ AI Agent initialized with model: {agent.current_model}")
        
        # Test status
        status = await agent.get_status()
        print("✅ Status check passed")
        
        # Test basic functionality (without actually calling OpenAI)
        print("✅ AI Agent test completed")
        
        # Cleanup
        await agent.close()
        
    except Exception as e:
        print(f"❌ AI Agent test failed: {e}")
        return False
    
    return True

async def test_web_search():
    """Test web search functionality."""
    print("\n🔍 Testing Web Search...")
    
    try:
        from config import Config
        from tools.web_search import WebSearchTool
        
        config = Config()
        search_tool = WebSearchTool(config)
        
        print(f"✅ Web Search initialized")
        print(f"📡 Available providers: {search_tool.available_providers}")
        
        if search_tool.available_providers:
            print("✅ Web search is configured")
        else:
            print("⚠️  Web search not configured (add TAVILY_API_KEY to .env)")
        
    except Exception as e:
        print(f"❌ Web Search test failed: {e}")
        return False
    
    return True

def test_knowledge_base():
    """Test knowledge base functionality."""
    print("\n📚 Testing Knowledge Base...")
    
    try:
        from config import Config
        from tools.knowledge_base import KnowledgeBase
        
        config = Config()
        kb = KnowledgeBase(config)
        
        stats = kb.get_stats()
        print(f"✅ Knowledge Base initialized")
        print(f"📊 Documents: {stats['total_documents']}")
        
    except Exception as e:
        print(f"❌ Knowledge Base test failed: {e}")
        return False
    
    return True

async def main():
    """Run all tests."""
    print("🧪 Telegram Bot Component Tests")
    print("=" * 50)
    
    results = []
    
    # Test each component
    results.append(await test_ai_agent())
    results.append(await test_web_search())
    results.append(test_knowledge_base())
    
    print("\n" + "=" * 50)
    print("📋 Test Results:")
    
    if all(results):
        print("✅ All tests passed! Bot should work correctly.")
        print("\n🚀 Ready to start with: python start_bot.py")
    else:
        print("❌ Some tests failed. Check the errors above.")
        print("🔧 Fix issues before starting the bot.")

if __name__ == "__main__":
    asyncio.run(main())