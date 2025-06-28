# tools/web_search.py - Perplexity-powered web search functionality

import asyncio
import logging
from typing import Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class WebSearchTool:
    """
    Web search tool powered by Perplexity AI
    Uses Perplexity's sonar-pro model for real-time web search and analysis
    """

    def __init__(self, config):
        self.config = config
        self.available_providers = self._get_available_providers()
        
        # Initialize Perplexity client if API key is available
        if config.PERPLEXITY_API_KEY:
            self.perplexity_client = AsyncOpenAI(
                api_key=config.PERPLEXITY_API_KEY,
                base_url="https://api.perplexity.ai"
            )
            self.default_provider = "perplexity"
            logger.info("Perplexity web search initialized")
        else:
            self.perplexity_client = None
            self.default_provider = None
            logger.warning("Perplexity API key not provided - web search disabled")

    def _get_available_providers(self) -> list:
        """Check which search providers are configured"""
        providers = []
        
        if self.config.PERPLEXITY_API_KEY:
            providers.append("perplexity")
            
        return providers

    async def search(self, query: str, provider: Optional[str] = None, max_results: int = 5) -> str:
        """
        Perform web search using Perplexity AI
        """
        if not self.available_providers:
            return self._no_search_fallback(query)

        provider = provider or self.default_provider

        try:
            if provider == "perplexity":
                return await self._search_perplexity(query)
            else:
                return self._no_search_fallback(query)

        except Exception as e:
            logger.error(f"Search error with {provider}: {e}")
            return f"❌ Search failed: {str(e)}"

    async def _search_perplexity(self, query: str) -> str:
        """
        Search using Perplexity AI - real-time web search with citations
        """
        if not self.perplexity_client:
            return self._no_search_fallback(query)

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful research assistant. Provide comprehensive, "
                        "well-sourced answers based on current web information. "
                        "Include relevant citations and organize your response clearly."
                    ),
                },
                {
                    "role": "user",
                    "content": query,
                },
            ]

            response = await self.perplexity_client.chat.completions.create(
                model="sonar-pro",
                messages=messages,
                max_tokens=1500,
                temperature=0.2,
            )

            # Extract the response content
            search_result = response.choices[0].message.content
            
            # Format the response nicely
            formatted_response = f"""
🔍 **Web Search Results for:** "{query}"

{search_result}

---
*Powered by Perplexity AI with real-time web access*
            """.strip()

            return formatted_response

        except Exception as e:
            logger.error(f"Perplexity API error: {e}")
            raise Exception(f"Perplexity search failed: {str(e)}")

    def _no_search_fallback(self, query: str) -> str:
        """Fallback response when no search providers are available"""
        return f"""
❌ **Web search not available**

To enable web search, you need to set up the Perplexity API:

**Setup Steps:**
1. Sign up at https://www.perplexity.ai/settings/api
2. Get your API key from the dashboard
3. Add `PERPLEXITY_API_KEY=your_key` to your .env file
4. Restart the bot

Your query: "{query}"

*Note: Perplexity provides real-time web search with AI-powered analysis and citations.*
        """

    async def close(self):
        """Close the Perplexity client if it exists"""
        if hasattr(self.perplexity_client, 'aclose'):
            try:
                await self.perplexity_client.aclose()
                logger.info("Perplexity client closed")
            except Exception as e:
                logger.error(f"Error closing Perplexity client: {e}")

    def get_status(self) -> dict:
        """Get web search tool status"""
        return {
            "provider": "perplexity",
            "available": bool(self.perplexity_client),
            "api_configured": bool(self.config.PERPLEXITY_API_KEY)
        }