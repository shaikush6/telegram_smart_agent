# config.py - Configuration management

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """
    Configuration class to manage all API keys and settings
    """

    def __init__(self):
        # Required API Keys
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

        # Optional API Keys for enhanced functionality
        self.PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")  # For web search

        # Bot Configuration
        self.MAX_MESSAGE_LENGTH = 4000
        self.MAX_CONVERSATION_HISTORY = 20
        self.DEFAULT_MODEL = "gpt-4"

        # File Processing Settings
        self.MAX_FILE_SIZE_MB = 50
        self.TEMP_DIR = "temp_files"
        self.KNOWLEDGE_BASE_DIR = "knowledge_base"

        # Rate Limiting
        self.MAX_REQUESTS_PER_MINUTE = 30
        self.MAX_TOKENS_PER_DAY = 100000

        # Validate required settings
        self._validate_config()

    def _validate_config(self):
        """Check that required environment variables are set"""
        required_vars = {
            "TELEGRAM_TOKEN": self.TELEGRAM_TOKEN,
            "OPENAI_API_KEY": self.OPENAI_API_KEY
        }

        missing_vars = [var for var, value in required_vars.items() if not value]

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                f"Please check your .env file."
            )

        # Create directories if they don't exist
        os.makedirs(self.TEMP_DIR, exist_ok=True)
        os.makedirs(self.KNOWLEDGE_BASE_DIR, exist_ok=True)

    def get_search_config(self):
        """Get available search configurations"""
        search_options = []

        if self.PERPLEXITY_API_KEY:
            search_options.append("perplexity")

        return search_options

    def __str__(self):
        """String representation for debugging (without exposing keys)"""
        return f"""
Config Status:
- Telegram Token: {'✅' if self.TELEGRAM_TOKEN else '❌'}
- OpenAI API Key: {'✅' if self.OPENAI_API_KEY else '❌'}
- Perplexity API Key: {'✅' if self.PERPLEXITY_API_KEY else '❌'}
- Default Model: {self.DEFAULT_MODEL}
        """