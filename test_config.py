#!/usr/bin/env python3
"""Quick test to check if configuration loads properly."""

try:
    from config import Config
    
    print("🔧 Testing bot configuration...")
    config = Config()
    print(config)
    print("✅ Configuration loaded successfully!")
    
    # Test basic imports
    print("\n📦 Testing imports...")
    import telegram
    import openai
    import aiohttp
    print("✅ All required packages imported successfully!")
    
    print("\n🎯 Ready to start bot!")
    
except Exception as e:
    print(f"❌ Configuration test failed: {e}")
    import traceback
    traceback.print_exc()