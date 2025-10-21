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
        self.SCRAPING_API_KEY = os.getenv("SCRAPING_API_KEY")      # For reliable web scraping
        self.ARCHIVE_API_KEY = os.getenv("ARCHIVE_API_KEY")        # For paid archiving providers

        # Database Configuration
        self.DB_NAME = os.getenv("DB_NAME", "shopsmart")
        self.DB_USER = os.getenv("DB_USER", "postgres")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
        self.DB_HOST = os.getenv("DB_HOST", "localhost")
        self.DB_PORT = os.getenv("DB_PORT", "5432")

        # Bot Configuration
        self.MAX_MESSAGE_LENGTH = 4000
        self.MAX_CONVERSATION_HISTORY = 20
        self.DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
        self.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

        # File Processing Settings
        self.MAX_FILE_SIZE_MB = 50
        self.TEMP_DIR = "temp_files"
        self.KNOWLEDGE_BASE_DIR = "knowledge_base"
        self.SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", os.path.join(self.TEMP_DIR, "screenshots"))

        # Rate Limiting
        self.MAX_REQUESTS_PER_MINUTE = 30
        self.MAX_TOKENS_PER_DAY = 100000

        # Rendering & Vision Enhancements
        self.RENDERER_URL = os.getenv("RENDERER_URL")
        self.RENDERER_API_KEY = os.getenv("RENDERER_API_KEY")
        self.RENDERER_TIMEOUT = int(os.getenv("RENDERER_TIMEOUT", "25"))
        self.RENDERER_MIN_WORDS = int(os.getenv("RENDERER_MIN_WORDS", "40"))
        self.ENABLE_RENDERER = os.getenv("ENABLE_RENDERER", "true").lower() not in {"false", "0", "no"}
        self.ENABLE_SCREENSHOT_OCR = os.getenv("ENABLE_SCREENSHOT_OCR", "true").lower() not in {"false", "0", "no"}
        self.VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini-vision")

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
        os.makedirs(self.SCREENSHOT_DIR, exist_ok=True)

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
- Embedding Model: {self.EMBEDDING_MODEL}
        """
