#!/usr/bin/env python3
"""
Simple Bot Starter Script
Run this to start your Telegram bot with better error handling.
"""

import sys
import os
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def check_requirements():
    """Check if all required packages are installed."""
    # Map package names to their import names
    package_imports = {
        'telegram': 'telegram',
        'openai': 'openai', 
        'python-dotenv': 'dotenv',
        'aiohttp': 'aiohttp',
        'beautifulsoup4': 'bs4'
    }
    
    missing = []
    for package_name, import_name in package_imports.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(package_name)
    
    if missing:
        print(f"❌ Missing required packages: {', '.join(missing)}")
        print(f"📦 Install them with: pip install {' '.join(missing)}")
        return False
    
    return True

def check_env_file():
    """Check if .env file exists and has required keys."""
    env_path = Path(__file__).parent / '.env'
    
    if not env_path.exists():
        print("❌ .env file not found!")
        print("📝 Create a .env file with your API keys")
        return False
    
    # Basic check for required variables
    with open(env_path) as f:
        content = f.read()
    
    required_vars = ['TELEGRAM_TOKEN', 'OPENAI_API_KEY']
    missing_vars = []
    
    for var in required_vars:
        if f"{var}=" not in content or f"{var}=your_" in content:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing or incomplete API keys: {', '.join(missing_vars)}")
        print("📝 Edit .env file and add your actual API keys")
        return False
    
    # Check for optional Perplexity API key
    if "PERPLEXITY_API_KEY=your_" in content or "PERPLEXITY_API_KEY=" not in content:
        print("⚠️  Perplexity API key not configured - web search will be disabled")
        print("💡 Add PERPLEXITY_API_KEY to .env to enable web search")
    
    return True

def main():
    """Main startup function."""
    print("🤖 Telegram Smart Agent Startup")
    print("=" * 40)
    
    # Check requirements
    print("📦 Checking Python packages...")
    if not check_requirements():
        sys.exit(1)
    print("✅ All packages installed")
    
    # Check environment
    print("🔑 Checking environment configuration...")
    if not check_env_file():
        sys.exit(1)
    print("✅ Environment configured")
    
    # Start bot
    print("🚀 Starting bot...")
    try:
        from main_bot import TelegramBot
        bot = TelegramBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot startup failed: {e}")
        logging.exception("Bot startup error")
        sys.exit(1)

if __name__ == "__main__":
    main()