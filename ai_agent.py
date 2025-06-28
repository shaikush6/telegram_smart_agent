# ai_agent.py - The brain of your smart agent

import openai
import asyncio
import json
import time
from typing import Dict, List, Optional
import logging
from datetime import datetime

# Import our tools (we'll create these)
from tools.web_search import WebSearchTool
from tools.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


class AIAgent:
    """
    The main AI agent that coordinates between OpenAI and various tools
    """

    def __init__(self, config):
        """Initialize the AI agent with configuration"""
        self.config = config

        # Set up OpenAI client (modern approach)
        try:
            self.client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise Exception(f"OpenAI client initialization failed: {e}. Try upgrading openai package.")

        # Current model (can be switched)
        self.current_model = config.DEFAULT_MODEL

        # Initialize tools
        self.web_search_tool = WebSearchTool(config)  # Renamed to avoid conflict with method
        self.knowledge_base = KnowledgeBase(config)

        # Track usage and conversation history
        self.usage_stats = {
            'messages_processed': 0,
            'tokens_used': 0,
            'searches_performed': 0,
            'files_processed': 0,
            'start_time': datetime.now()
        }

        # Simple conversation memory (per user)
        self.conversation_history: Dict[int, List[Dict]] = {}

        # System prompt for the AI
        self.system_prompt = """
You are a helpful, intelligent assistant with access to web search and knowledge tools.

Your capabilities:
- Natural conversation and question answering
- Web search and article analysis
- Document processing and knowledge retrieval
- Audio/video transcription and analysis

Guidelines:
- Be concise but thorough
- Use markdown formatting for better readability
- When searching the web, provide summaries with key insights
- Cite sources when referencing specific information
- Ask clarifying questions if the user's request is unclear
- Be friendly and conversational

Always think step by step when handling complex requests.
        """

    async def close(self):
        """Gracefully close any asynchronous resources like the OpenAI client."""
        if hasattr(self.client, 'aclose') and asyncio.iscoroutinefunction(
                self.client.aclose):  # OpenAI v1.x uses aclose
            logger.info("Closing OpenAI client session (aclose)...")
            await self.client.aclose()
        elif hasattr(self.client, 'close') and asyncio.iscoroutinefunction(self.client.close):
            logger.info("Closing OpenAI client session (close)...")
            await self.client.close()
        else:
            logger.info("OpenAI client does not have a recognized async close method or is not an AsyncOpenAI client.")

        # Close web search tool if it has async resources
        if hasattr(self.web_search_tool, 'close'):
            try:
                await self.web_search_tool.close()
            except Exception as e:
                logger.error(f"Error closing web search tool: {e}")
        
        # Close knowledge base if it has async resources
        if hasattr(self.knowledge_base, 'close'):
            try:
                await self.knowledge_base.close()
            except Exception as e:
                logger.error(f"Error closing knowledge base: {e}")

    def switch_model(self, model_name: str):
        """Switch between different OpenAI models"""
        self.current_model = model_name
        logger.info(f"Switched to model: {model_name}")

    async def chat(self, message: str, user_id: int) -> str:
        """
        Main chat function - handles regular conversation
        """
        try:
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []

            self.conversation_history[user_id].append({
                "role": "user",
                "content": message
            })

            if len(self.conversation_history[user_id]) > 20:  # 10 exchanges
                self.conversation_history[user_id] = self.conversation_history[user_id][-20:]

            if await self._should_search_web(message):
                return await self._handle_with_search(message, user_id)

            messages = [
                           {"role": "system", "content": self.system_prompt}
                       ] + self.conversation_history[user_id]

            response = await self.client.chat.completions.create(
                model=self.current_model,
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )

            ai_response = response.choices[0].message.content

            self.conversation_history[user_id].append({
                "role": "assistant",
                "content": ai_response
            })

            self.usage_stats['messages_processed'] += 1
            if response.usage:  # Ensure usage is available
                self.usage_stats['tokens_used'] += response.usage.total_tokens

            return ai_response

        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing your message. Please try again."

    async def _should_search_web(self, message: str) -> bool:
        search_keywords = [
            'search', 'find', 'latest', 'recent', 'news', 'current',
            'what happened', 'update on', 'look up', 'research'
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in search_keywords)

    async def _handle_with_search(self, message: str, user_id: int) -> str:
        try:
            search_results = await self.web_search_tool.search(message)  # Use renamed attribute

            analysis_prompt = f"""
Based on the following web search results for the query "{message}", provide a comprehensive and helpful response:

Search Results:
{search_results}

Please:
1. Summarize the key findings
2. Highlight the most important insights
3. Provide a clear, organized response
4. Include relevant links if available

Keep the response conversational and helpful.
            """

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": analysis_prompt}
            ]

            response = await self.client.chat.completions.create(
                model=self.current_model,
                messages=messages,
                max_tokens=1500,
                temperature=0.7
            )
            ai_response = response.choices[0].message.content
            self.usage_stats['searches_performed'] += 1
            if response.usage:  # Ensure usage is available
                self.usage_stats['tokens_used'] += response.usage.total_tokens
            return ai_response
        except Exception as e:
            logger.error(f"Search handling error: {e}", exc_info=True)
            return "I had trouble searching for that information. Please try rephrasing your request."

    async def web_search(self, query: str) -> str:  # This is the method called by /search command
        try:
            search_results = await self.web_search_tool.search(query)  # Use renamed attribute

            analysis_prompt = f"""
Web search results for: "{query}"

{search_results}

Please provide:
1. A brief summary of what was found
2. Key insights and highlights
3. Top 3 most relevant results with brief descriptions
4. Any important trends or patterns

Format with markdown for readability.
            """
            response = await self.client.chat.completions.create(
                model=self.current_model,
                messages=[
                    {"role": "system", "content": "You are a research assistant analyzing web search results."},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=1200,
                temperature=0.7
            )
            self.usage_stats['searches_performed'] += 1
            if response.usage:  # Ensure usage is available
                self.usage_stats['tokens_used'] += response.usage.total_tokens
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Web search error: {e}", exc_info=True)
            return "❌ Web search failed. Please check your internet connection and try again."

    async def process_audio(self, file_path: str) -> str:
        try:
            with open(file_path, 'rb') as audio_file:
                transcript_response = await self.client.audio.transcriptions.create(  # Renamed for clarity
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"  # This should directly return text if supported, or parse if it's an object
                )

            # Assuming transcript_response is directly the text, adjust if it's an object
            transcript = transcript_response if isinstance(transcript_response, str) else transcript_response.text

            analysis_prompt = f"""
I've transcribed an audio message. Here's what was said:

"{transcript}"

Please:
1. Provide a brief summary if it's long
2. Respond naturally to the content
3. Ask relevant follow-up questions if appropriate

Respond as if this was a regular conversation.
            """
            response = await self.client.chat.completions.create(
                model=self.current_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=800,
                temperature=0.7
            )
            ai_response = response.choices[0].message.content
            full_response = f"**🎤 Transcript:**\n\"{transcript}\"\n\n**📝 My Response:**\n{ai_response}"
            self.usage_stats['files_processed'] += 1
            if response.usage:  # Ensure usage is available
                self.usage_stats['tokens_used'] += response.usage.total_tokens
            return full_response
        except Exception as e:
            logger.error(f"Audio processing error: {e}", exc_info=True)
            return "❌ Couldn't process the audio file. Make sure it's a valid audio format."

    async def process_video(self, file_path: str) -> str:
        """
        Process video files - extract audio and transcribe
        """
        try:
            import os
            import subprocess
            
            # Extract audio from video using ffmpeg
            audio_path = file_path.replace('.mp4', '.mp3').replace('.mov', '.mp3').replace('.avi', '.mp3')
            
            # Use ffmpeg to extract audio
            try:
                subprocess.run([
                    'ffmpeg', '-i', file_path, '-vn', '-acodec', 'mp3', 
                    '-ar', '44100', '-ac', '2', audio_path, '-y'
                ], check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                return "❌ Failed to extract audio from video. Make sure ffmpeg is installed."
            except FileNotFoundError:
                return "❌ ffmpeg not found. Please install ffmpeg to process videos."
            
            # Now transcribe the extracted audio
            try:
                with open(audio_path, 'rb') as audio_file:
                    transcript_response = await self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="text"
                    )
                
                transcript = transcript_response if isinstance(transcript_response, str) else transcript_response.text
                
                # Clean up extracted audio file
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                
                analysis_prompt = f"""
I've transcribed the audio from a video file. Here's what was said:

"{transcript}"

Please:
1. Provide a brief summary of the video content
2. Identify key topics or themes discussed
3. Respond naturally to the content
4. Ask relevant follow-up questions if appropriate

Respond as if this was a regular conversation about video content.
                """
                
                response = await self.client.chat.completions.create(
                    model=self.current_model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": analysis_prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )
                
                ai_response = response.choices[0].message.content
                full_response = f"**🎥 Video Transcript:**\n\"{transcript}\"\n\n**📝 My Analysis:**\n{ai_response}"
                
                self.usage_stats['files_processed'] += 1
                if response.usage:
                    self.usage_stats['tokens_used'] += response.usage.total_tokens
                
                return full_response
                
            except Exception as e:
                # Clean up audio file if transcription fails
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                logger.error(f"Video transcription error: {e}")
                return f"❌ Couldn't transcribe video audio: {str(e)}"
                
        except Exception as e:
            logger.error(f"Video processing error: {e}", exc_info=True)
            return "❌ Couldn't process the video file. Make sure it's a valid video format."

    async def process_document(self, file_path: str, file_name: str) -> str:
        """
        Process document files (PDF, TXT, DOCX, etc.)
        """
        try:
            import os
            from pathlib import Path
            
            file_extension = Path(file_name).suffix.lower()
            content = ""
            
            if file_extension == '.txt':
                # Handle text files
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
            elif file_extension == '.pdf':
                # Handle PDF files
                try:
                    import PyPDF2
                    with open(file_path, 'rb') as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        content = ""
                        for page in pdf_reader.pages:
                            content += page.extract_text() + "\n"
                except ImportError:
                    return "❌ PDF processing requires PyPDF2. Install with: pip install PyPDF2"
                    
            elif file_extension in ['.docx', '.doc']:
                # Handle Word documents
                try:
                    import docx
                    doc = docx.Document(file_path)
                    content = "\n".join([paragraph.text for paragraph in doc.paragraphs])
                except ImportError:
                    return "❌ Word document processing requires python-docx. Install with: pip install python-docx"
                    
            else:
                return f"❌ Unsupported file type: {file_extension}. Supported types: .txt, .pdf, .docx"
            
            if not content.strip():
                return "❌ No text content found in the document."
            
            # Truncate very long documents
            if len(content) > 10000:
                content = content[:10000] + "\n\n[Document truncated - showing first 10,000 characters]"
            
            # Analyze the document with AI
            analysis_prompt = f"""
I've extracted text from a document titled "{file_name}". Here's the content:

{content}

Please:
1. Provide a brief summary of the document
2. Identify the main topics or themes
3. Extract key points or insights
4. Answer any questions I might have about it

Organize your response clearly and be helpful.
            """
            
            response = await self.client.chat.completions.create(
                model=self.current_model,
                messages=[
                    {"role": "system", "content": "You are a helpful document analysis assistant."},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=1200,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            full_response = f"**📄 Document Analysis: {file_name}**\n\n{ai_response}"
            
            self.usage_stats['files_processed'] += 1
            if response.usage:
                self.usage_stats['tokens_used'] += response.usage.total_tokens
            
            return full_response
            
        except Exception as e:
            logger.error(f"Document processing error: {e}", exc_info=True)
            return f"❌ Couldn't process the document: {str(e)}"

    async def process_image(self, file_path: str, user_query: str = "Analyze this image") -> str:
        """
        Process image files using OpenAI's vision model
        """
        try:
            import base64
            import os
            
            # Read and encode the image
            with open(file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Determine image format
            file_extension = os.path.splitext(file_path)[1].lower()
            if file_extension in ['.jpg', '.jpeg']:
                image_format = "jpeg"
            elif file_extension == '.png':
                image_format = "png"
            elif file_extension == '.gif':
                image_format = "gif"
            elif file_extension == '.webp':
                image_format = "webp"
            else:
                image_format = "jpeg"  # Default fallback
            
            # Create the vision prompt
            vision_prompt = f"""
Analyze this image and respond to the user's request: "{user_query}"

Please provide:
1. A detailed description of what you see in the image
2. Any relevant information, context, or insights
3. Answer any specific questions the user might have
4. If there's text in the image, transcribe it
5. Identify objects, people, places, or activities if relevant

Be thorough but conversational in your response.
            """
            
            # Call OpenAI's vision API
            response = await self.client.chat.completions.create(
                model="gpt-4o",  # Use GPT-4 with vision capabilities
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": vision_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            full_response = f"**🖼️ Image Analysis:**\n\n{ai_response}"
            
            self.usage_stats['files_processed'] += 1
            if response.usage:
                self.usage_stats['tokens_used'] += response.usage.total_tokens
            
            return full_response
            
        except Exception as e:
            logger.error(f"Image processing error: {e}", exc_info=True)
            return f"❌ Couldn't process the image: {str(e)}"

    async def get_status(self) -> str:
        uptime = datetime.now() - self.usage_stats['start_time']
        # Ensure tokens_used is an integer before formatting
        tokens_used_val = int(self.usage_stats.get('tokens_used', 0))

        status = f"""
**🤖 Bot Status**

**Current Configuration:**
• Model: `{self.current_model}`
• Uptime: {str(uptime).split('.')[0]}

**Usage Statistics:**
• Messages processed: {self.usage_stats['messages_processed']}
• Tokens used: {tokens_used_val:,}
• Web searches: {self.usage_stats['searches_performed']}
• Files processed: {self.usage_stats['files_processed']}

**Estimated Cost (Illustrative - check current OpenAI pricing):**
• GPT-4 (assuming $0.03/1K input, $0.06/1K output - using a rough estimate): ~${(tokens_used_val * 0.000045):.4f} 
• GPT-3.5-turbo (assuming $0.0005/1K input, $0.0015/1K output - using a rough estimate): ~${(tokens_used_val * 0.000001):.4f}

**Active Tools:**
• ✅ Web Search
• ✅ Audio Transcription
• 🚧 Video Processing (coming soon)
• 🚧 Document Processing (coming soon)
• 🚧 Knowledge Base (coming soon)
        """
        return status