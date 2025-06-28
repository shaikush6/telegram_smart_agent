# main_bot.py - Your Telegram Smart Agent Entry Point

import logging
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import os
from dotenv import load_dotenv

# Import our custom modules
from ai_agent import AIAgent
from config import Config

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self):
        """Initialize the bot with configuration and AI agent"""
        self.config = Config()
        self.ai_agent = AIAgent(self.config)
        self.application = Application.builder().token(self.config.TELEGRAM_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Define what commands and messages the bot responds to"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("model", self.model_command))
        self.application.add_handler(CommandHandler("search", self.search_command))
        self.application.add_handler(CommandHandler("status", self.status_command))

        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        self.application.add_handler(MessageHandler(filters.AUDIO, self.handle_audio))
        self.application.add_handler(MessageHandler(filters.VIDEO, self.handle_video))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = """
🤖 **Smart Agent Bot Ready!**

I can help you with:
• 💬 Natural conversation (powered by OpenAI)
• 🔍 Web search with real-time data (Perplexity)
• 📄 Document analysis (PDF, Word, TXT)
• 🖼️ Image analysis and description (AI Vision)
• 🎤 Audio/voice transcription and analysis
• 🎥 Video processing (audio extraction + transcription)
• 🧠 Knowledge base storage

**Commands:**
/help - Show detailed help
/model - Switch AI models or check current
/search [query] - Web search
/status - Bot status and usage

**Send me files:**
📱 Photos - AI vision analysis
📄 Documents - Text extraction & analysis  
🎵 Audio/Voice - Transcription & discussion
🎥 Videos - Audio extraction & transcription

Just send me a message to start chatting!
        """
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
🔧 **Available Commands:**

**Model Management:**
• `/model` - Show current AI model
• `/model gpt4` - Switch to GPT-4 (e.g., gpt-4, gpt-4-turbo)
• `/model gpt35` - Switch to GPT-3.5 (e.g., gpt-3.5-turbo)

**Search & Analysis:**
• `/search [your query]` - Web search with AI summary
• Send any message - Chat with AI

**File Processing:**
• Send PDF (soon) - Extract and analyze text
• Send audio/voice - Transcribe and discuss
• Send video (soon) - Extract audio, transcribe, analyze frames

**Utilities:**
• `/status` - Check bot health and usage stats
• `/help` - This help message

**Tips:**
• Be specific in your requests
• Ask follow-up questions
        """
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if not args:
            current_model = self.ai_agent.current_model
            # Example model info (actual pricing/features vary by specific model version)
            model_info_text = {
                'gpt-4': '🧠 GPT-4 - Highly capable, supports longer context.',
                'gpt-4-turbo': '🚀 GPT-4 Turbo - Optimized for speed and cost, large context.',
                'gpt-3.5-turbo': '⚡ GPT-3.5 Turbo - Fast and cost-effective for general tasks.'
            }
            status_text = f"""
**Current Model:** `{current_model}`
{model_info_text.get(current_model, 'An OpenAI model.')}

**To switch, use (examples):**
• `/model gpt-4`
• `/model gpt-4-turbo`
• `/model gpt-3.5-turbo` 
(Ensure the model name is exactly as supported by OpenAI API)
            """
            await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
        else:
            model_arg = args[0].lower()
            # Allow direct model names or simple aliases
            model_map = {
                'gpt4': 'gpt-4',  # A common alias
                'gpt35': 'gpt-3.5-turbo',  # A common alias
            }
            new_model = model_map.get(model_arg, model_arg)  # Use arg directly if not in map

            # Basic validation (you might want to check against a list of known valid models)
            if "gpt-4" in new_model or "gpt-3.5" in new_model:
                self.ai_agent.switch_model(new_model)
                await update.message.reply_text(f"✅ Switched to **{new_model}**", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text(
                    f"❌ Unknown or unsupported model alias: {model_arg}. Provide a valid OpenAI model name.",
                    parse_mode=ParseMode.MARKDOWN)

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Please provide a search query. Example: `/search AI news 2025`")
            return
        query = ' '.join(context.args)
        await update.message.reply_text("🔍 Searching the web for you...", parse_mode=ParseMode.MARKDOWN)
        try:
            result = await self.ai_agent.web_search(query)
            await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Search command error: {e}", exc_info=True)
            await update.message.reply_text("❌ Search failed. Please try again later.")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        status = await self.ai_agent.get_status()
        await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_message = update.message.text
        user_id = update.effective_user.id
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        try:
            response = await self.ai_agent.chat(user_message, user_id)
            if len(response) > 4000:  # Telegram message length limit
                parts = [response[i:i + 4000] for i in range(0, len(response), 4000)]
                for part in parts:
                    await update.message.reply_text(part, parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Message handling error: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Sorry, I encountered an error processing your message. Please try again.")

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🎤 Processing voice message...", parse_mode=ParseMode.MARKDOWN)
        file_id = update.message.voice.file_id
        temp_dir = self.config.TEMP_DIR  # Get temp_dir from config
        try:
            voice_file = await context.bot.get_file(file_id)
            # Ensure temp_dir exists (config should handle this, but double check)
            os.makedirs(temp_dir, exist_ok=True)
            file_path = os.path.join(temp_dir, f"voice_{update.effective_user.id}_{file_id}.ogg")
            await voice_file.download_to_drive(custom_path=file_path)

            response = await self.ai_agent.process_audio(file_path)
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Voice processing error: {e}", exc_info=True)
            await update.message.reply_text("❌ Couldn't process voice message. Please try again.")
            # Optional: attempt to clean up file if path was defined
            if 'file_path' in locals() and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e_clean:
                    logger.error(f"Error cleaning up voice file {file_path}: {e_clean}", exc_info=True)

    async def handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle audio files (similar to voice but for generic audio uploads)"""
        await update.message.reply_text("🎵 Processing audio file...", parse_mode=ParseMode.MARKDOWN)
        file_id = update.message.audio.file_id
        file_name = update.message.audio.file_name or f"audio_{update.effective_user.id}_{file_id}.mp3"  # Guess extension
        temp_dir = self.config.TEMP_DIR

        try:
            audio_file_obj = await context.bot.get_file(file_id)
            os.makedirs(temp_dir, exist_ok=True)
            file_path = os.path.join(temp_dir, file_name)
            await audio_file_obj.download_to_drive(custom_path=file_path)

            response = await self.ai_agent.process_audio(file_path)  # Re-use process_audio
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Audio file processing error: {e}", exc_info=True)
            await update.message.reply_text("❌ Couldn't process the audio file. Please try again.")
            if 'file_path' in locals() and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e_clean:
                    logger.error(f"Error cleaning up audio file {file_path}: {e_clean}", exc_info=True)

    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video files - extract audio and transcribe"""
        await update.message.reply_text("🎥 Processing video file...", parse_mode=ParseMode.MARKDOWN)
        file_id = update.message.video.file_id
        file_name = getattr(update.message.video, 'file_name', f"video_{update.effective_user.id}_{file_id}.mp4")
        temp_dir = self.config.TEMP_DIR

        try:
            video_file_obj = await context.bot.get_file(file_id)
            os.makedirs(temp_dir, exist_ok=True)
            file_path = os.path.join(temp_dir, file_name)
            await video_file_obj.download_to_drive(custom_path=file_path)

            response = await self.ai_agent.process_video(file_path)
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Video file processing error: {e}", exc_info=True)
            await update.message.reply_text("❌ Couldn't process the video file. Please try again.")
            if 'file_path' in locals() and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e_clean:
                    logger.error(f"Error cleaning up video file {file_path}: {e_clean}")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document files - extract text and analyze"""
        await update.message.reply_text("📄 Processing document...", parse_mode=ParseMode.MARKDOWN)
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name or f"document_{update.effective_user.id}_{file_id}.txt"
        temp_dir = self.config.TEMP_DIR

        try:
            # Check file size (Telegram limit is 20MB, but we can set our own limit)
            file_size = update.message.document.file_size
            if file_size and file_size > self.config.MAX_FILE_SIZE_MB * 1024 * 1024:
                await update.message.reply_text(f"❌ File too large. Maximum size: {self.config.MAX_FILE_SIZE_MB}MB")
                return

            document_file_obj = await context.bot.get_file(file_id)
            os.makedirs(temp_dir, exist_ok=True)
            file_path = os.path.join(temp_dir, file_name)
            await document_file_obj.download_to_drive(custom_path=file_path)

            response = await self.ai_agent.process_document(file_path, file_name)
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Document processing error: {e}", exc_info=True)
            await update.message.reply_text("❌ Couldn't process the document. Please try again.")
            if 'file_path' in locals() and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e_clean:
                    logger.error(f"Error cleaning up document file {file_path}: {e_clean}")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo/image files - analyze with AI vision"""
        await update.message.reply_text("🖼️ Analyzing image...", parse_mode=ParseMode.MARKDOWN)
        
        # Get the largest photo size
        photo = update.message.photo[-1]  # Last element is highest resolution
        file_id = photo.file_id
        temp_dir = self.config.TEMP_DIR

        try:
            photo_file_obj = await context.bot.get_file(file_id)
            os.makedirs(temp_dir, exist_ok=True)
            file_path = os.path.join(temp_dir, f"photo_{update.effective_user.id}_{file_id}.jpg")
            await photo_file_obj.download_to_drive(custom_path=file_path)

            # Get caption if provided
            caption = update.message.caption or "Analyze this image"
            response = await self.ai_agent.process_image(file_path, caption)
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Photo processing error: {e}", exc_info=True)
            await update.message.reply_text("❌ Couldn't process the image. Please try again.")
            if 'file_path' in locals() and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e_clean:
                    logger.error(f"Error cleaning up photo file {file_path}: {e_clean}")

    # -----------------------------------------------
    # NEW synchronous run() – no async / await here
    # -----------------------------------------------
    def run(self):
        """Start polling and handle graceful shutdown."""
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help information"),
            BotCommand("model", "Switch AI models"),
            BotCommand("search", "Web search"),
            BotCommand("status", "Bot status"),
        ]

        try:
            # Set commands and start polling
            import asyncio
            
            # Check if we already have an event loop
            try:
                loop = asyncio.get_running_loop()
                logger.info("Using existing event loop")
            except RuntimeError:
                # Create new event loop if none exists
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                logger.info("Created new event loop")

            # Set commands
            loop.run_until_complete(self.application.bot.set_my_commands(commands))
            logger.info("Bot commands set successfully")

            logger.info("🚀 Starting bot polling...")
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )

        except Exception as e:
            logger.error(f"Error during bot execution: {e}")
        finally:
            # Graceful shutdown
            try:
                if hasattr(self.ai_agent, "close") and asyncio.iscoroutinefunction(self.ai_agent.close):
                    logger.info("Closing AI-agent resources...")
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(self.ai_agent.close())
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
            
            logger.info("🛑 Bot stopped successfully")



# Main entry point
if __name__ == "__main__":
    print("🤖 Starting Telegram Smart Agent...")
    bot = TelegramBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user (KeyboardInterrupt).")
        print("\n👋 Bot stopped by user")