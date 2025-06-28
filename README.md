# 🤖 Telegram Smart Agent

An intelligent Telegram bot powered by OpenAI with web search capabilities, voice processing, and multi-modal features.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd /Users/shai-shalomhadad/PycharmProjects/telegram-smart-agent
pip install -r requirements.txt
```

### 2. Configure API Keys
Edit the `.env` file with your actual API keys:

```bash
# Required
TELEGRAM_TOKEN=your_actual_telegram_bot_token
OPENAI_API_KEY=your_actual_openai_api_key

# Optional (for web search)
TAVILY_API_KEY=your_tavily_api_key
```

### 3. Start the Bot

**Option A: Simple Start**
```bash
python start_bot.py
```

**Option B: Direct Start**
```bash
python main_bot.py
```

### 4. Stop the Bot
Press `Ctrl+C` in the terminal to stop the bot gracefully.

## 🔧 Getting API Keys

### Telegram Bot Token
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the token to your `.env` file

### OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy it to your `.env` file

### Perplexity API Key (Optional - for web search)
1. Sign up at [Perplexity.ai](https://www.perplexity.ai/settings/api)
2. Get your API key from the dashboard
3. Add to `.env` file

## 🎯 Features

- **💬 AI Chat**: Natural conversation with GPT-4
- **🔍 Web Search**: Real-time web search with AI summaries  
- **🎤 Voice Processing**: Transcribe and respond to voice messages
- **📱 Commands**: `/help`, `/search`, `/model`, `/status`
- **🔄 Model Switching**: Switch between GPT models on the fly

## 📋 Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and feature overview |
| `/help` | Detailed help and usage instructions |
| `/search [query]` | Perform web search with AI analysis |
| `/model` | Check current model or switch models |
| `/status` | Bot status, usage stats, and health check |

## 🛠️ Troubleshooting

### Bot Not Responding
1. Check that the bot is running in terminal
2. Verify `TELEGRAM_TOKEN` in `.env` is correct
3. Ensure the bot was started with [@BotFather](https://t.me/BotFather)

### OpenAI Errors
1. Verify `OPENAI_API_KEY` in `.env` is valid
2. Check your OpenAI account has credits
3. Ensure model name (like `gpt-4`) is accessible to your account

### Web Search Not Working
1. Add `PERPLEXITY_API_KEY` to `.env` file
2. Check Perplexity account credits
3. Bot will show fallback message if search unavailable

### Dependencies Issues
```bash
pip install --upgrade -r requirements.txt
```

## 🔄 Starting/Stopping

### To Start:
```bash
# Navigate to bot directory
cd /Users/shai-shalomhadad/PycharmProjects/telegram-smart-agent

# Start with error checking
python start_bot.py

# Or start directly
python main_bot.py
```

### To Stop:
- Press `Ctrl+C` in the terminal
- The bot will shut down gracefully

### Background Running (Optional):
```bash
# Run in background (Linux/Mac)
nohup python start_bot.py > bot.log 2>&1 &

# To stop background process
pkill -f "python start_bot.py"
```

## 📁 Project Structure

```
telegram-smart-agent/
├── main_bot.py          # Main bot entry point
├── start_bot.py         # Enhanced startup script  
├── ai_agent.py          # AI logic and OpenAI integration
├── config.py            # Configuration management
├── .env                 # API keys (keep secure!)
├── requirements.txt     # Python dependencies
├── tools/
│   ├── web_search.py    # Web search functionality
│   └── knowledge_base.py # Knowledge base (future)
├── temp_files/          # Temporary file storage
└── knowledge_base/      # Knowledge base storage
```

## 🔐 Security Notes

- **Never commit `.env` file** to version control
- Keep API keys secure and rotate regularly  
- Monitor usage to avoid unexpected charges
- The bot processes messages - ensure appropriate user access

---

**Need Help?** Check the logs in terminal when running the bot for detailed error messages.