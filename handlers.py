import csv
import io
import logging
import re
from datetime import datetime
from html import escape
from typing import Any, Dict, List, Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import database
from link_archiver import archive_link
from link_intelligence import analyze_text_content, generate_embedding
from link_processor import process_url
from link_retriever import find_links_by_query

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(
    r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\."
    r"[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.add_user(user.id, user.username)
    await update.message.reply_text(
        "Welcome to Silo! 🧠 Your intelligent link manager.\n\n"
        "Send me a link and I will fetch the metadata, extract key topics, and make it searchable.\n"
        "Use /help to see everything I can do."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<b>Silo — Your Intelligent Link Manager</b>\n\n"
        "Save, organise, and rediscover the links your team shares.\n\n"
        "<b>Commands</b>\n"
        "• /recent — Show your latest saved links\n"
        "• /search &lt;query&gt; — Search your saved links\n"
        "• /stats — Quick stats about your knowledge base\n"
        "• /export — Download a CSV of your links\n"
        "• /archive &lt;url&gt; — Capture a snapshot of a page\n"
        "• /help — Show this menu\n\n"
        "<b>Try queries like</b>\n"
        "• articles about onboarding from last week\n"
        "• video shared by Sarah about marketing\n"
        "• form we filled out yesterday\n"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.add_user(user.id, user.username)
    links = database.get_recent_links(user.id, limit=5)

    if not links:
        await update.message.reply_text("No links yet. Share a URL and I'll save it for you.")
        return

    message = "\n\n".join(_render_link_entry(link) for link in links)
    await update.message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.add_user(user.id, user.username)

    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Please provide a search query, e.g. <code>/search articles about AI</code>", parse_mode=ParseMode.HTML)
        return

    results = find_links_by_query(user.id, query, limit=7)
    if not results:
        await update.message.reply_text("I couldn't find anything for that query yet. Try different keywords or add more context.")
        return

    header = f"<b>Search results for:</b> {escape(query)}"
    body = "\n\n".join(_render_link_entry(link) for link in results)
    await update.message.reply_text(f"{header}\n\n{body}", parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.add_user(user.id, user.username)
    stats = database.get_link_stats(user.id)

    if stats["total_links"] == 0:
        await update.message.reply_text("No stats yet — start by saving a link.")
        return

    top_categories = ", ".join(
        f"{row['category']} ({row['count']})" for row in stats["top_categories"]
    ) or "—"
    top_domains = ", ".join(
        f"{row['domain']} ({row['count']})" for row in stats["top_domains"]
    ) or "—"

    last_saved = stats["last_saved_at"]
    last_saved_str = last_saved.strftime("%d %b %Y %H:%M") if last_saved else "—"

    message = (
        "<b>📊 Your Silo Stats</b>\n"
        f"• Total links: <b>{stats['total_links']}</b>\n"
        f"• Last saved: {escape(last_saved_str)}\n"
        f"• Top categories: {escape(top_categories)}\n"
        f"• Top domains: {escape(top_domains)}"
    )
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.add_user(user.id, user.username)
    links = database.get_links_for_export(user.id)

    if not links:
        await update.message.reply_text("Nothing to export yet — send me a link first.")
        return

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Title",
            "URL",
            "Summary",
            "Description",
            "Domain",
            "Categories",
            "Entities",
            "Author",
            "Content Type",
            "Published",
            "Created At",
            "Updated At",
            "Snapshots",
        ]
    )

    for link in links:
        writer.writerow(
            [
                link.get("title") or "",
                link.get("url") or "",
                link.get("ai_summary") or "",
                link.get("description") or "",
                link.get("domain") or "",
                ", ".join(link.get("categories") or []),
                ", ".join(link.get("entities") or []),
                link.get("author") or "",
                link.get("content_type") or "",
                link.get("publish_date") or "",
                link.get("created_at") or "",
                link.get("updated_at") or "",
                ", ".join(link.get("snapshots") or []),
            ]
        )

    csv_bytes = buffer.getvalue().encode("utf-8")
    filename = f"silo_links_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    file_like = io.BytesIO(csv_bytes)
    file_like.name = filename

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=file_like,
        filename=filename,
        caption="Here is your Silo export.",
    )


async def archive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.add_user(user.id, user.username)

    url = " ".join(context.args).strip()
    if not url:
        await update.message.reply_text("Please provide a URL to archive, e.g. <code>/archive https://example.com</code>", parse_mode=ParseMode.HTML)
        return

    link_id = database.add_link(user.id, url)
    if not link_id:
        await update.message.reply_text("I couldn't register that link. Please try again.")
        return

    snapshot_path = await archive_link(link_id, url)
    if snapshot_path:
        await update.message.reply_text(
            f"Snapshot saved. You can find it at:\n<code>{escape(snapshot_path)}</code>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text("I couldn't capture an archive right now. Please try again later.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages containing links or natural language queries."""
    user = update.effective_user
    database.add_user(user.id, user.username)

    message_text = (update.message.text or "").strip()
    urls = URL_PATTERN.findall(message_text)

    if urls:
        await handle_urls(update, user.id, urls)
        return

    await handle_natural_language_query(update, user.id, message_text)


async def handle_urls(update: Update, user_id: int, urls: List[str]):
    """Process and save detected URLs."""
    results: List[Dict[str, str]] = []
    user_note = _extract_user_note(update.message.text or "")

    for url in urls:
        logger.info("Processing link shared by %s: %s", user_id, url)
        try:
            page = process_url(url)
            if not page:
                # More informative error message with encouragement to add context
                results.append({
                    "status": "error", 
                    "message": f"⚠️ I couldn't read the content from {url}. This might be due to:\n"
                              "• Login required\n• JavaScript-heavy page\n• Regional restrictions\n• Network issues\n\n"
                              "💡 I can still save the link! Just add some context about what this link is for, "
                              "and I'll store it with your description so you can find it later."
                })
                
                # Still try to save the link with user context if provided
                if user_note:
                    try:
                        link_id = database.add_link(user_id, url, description=user_note)
                        if link_id:
                            database.update_link_details(link_id, ai_summary=f"Saved with user context: {user_note}")
                            database.record_link_source(link_id, shared_by_user_id=user_id, platform="telegram")
                            results.append({
                                "status": "saved_context_only",
                                "message": f"✅ Link saved with your context: \"{user_note}\"\n"
                                          f"🔍 You can search for it later using your description."
                            })
                    except Exception as save_exc:
                        logger.warning("Failed to save link with user context: %s", save_exc)
                continue

            metadata = page["metadata"]
            resolved_url = page.get("resolved_url", url)
            link_description = metadata.get("description") or (user_note or None)
            screenshot_path = page.get("screenshot_path")
            extraction_method = page.get("extraction_method")
            link_id = database.add_link(
                user_id,
                resolved_url,
                title=metadata.get("title"),
                description=link_description,
                domain=metadata.get("domain"),
            )

            if not link_id:
                results.append({"status": "error", "message": f"⚠️ Couldn't save {resolved_url}"})
                continue

            database.update_link_details(
                link_id,
                title=metadata.get("title"),
                description=link_description,
                domain=metadata.get("domain"),
                screenshot_path=screenshot_path,
                archived_html=page.get("html"),
            )
            database.add_link_metadata(link_id, metadata)

            text_content = (page["text_content"] or "").strip()
            ai_analysis = None
            categories: List[str] = []
            entities: List[Dict[str, Any]] = []
            warning: Optional[str] = None

            if text_content:
                ai_analysis = await analyze_text_content(text_content, user_context=user_note)

                categories = ai_analysis.get("categories") or []
                if categories:
                    database.add_link_categories(link_id, categories)

                entities = ai_analysis.get("entities") or []
                if entities:
                    database.add_link_entities(link_id, entities)

                database.update_link_details(link_id, ai_summary=ai_analysis.get("summary"))

                embedding_payload = await generate_embedding(text_content[:4000])
                if embedding_payload and embedding_payload.get("vector"):
                    database.store_link_embedding(
                        link_id,
                        embedding_payload["vector"],
                        embedding_payload["model"],
                    )
            else:
                # Graceful handling when no text content is available
                if user_note:
                    fallback_summary = f"Saved with your description: {user_note}"
                    database.update_link_details(link_id, ai_summary=fallback_summary)
                    warning = (
                        "📄 I couldn't read the page content, but I've saved your link with the context you provided. "
                        "You can search for it using your description!"
                    )
                else:
                    fallback_summary = metadata.get("description") or "Link saved. Next time, add a description to make it easier to find!"
                    database.update_link_details(link_id, ai_summary=fallback_summary)
                    warning = (
                        "📄 I couldn't read the page content (it might require login or have heavy JavaScript). "
                        "💡 Next time, try adding a description like: 'This is a tutorial about...' or 'Important docs for...'"
                    )

            database.record_link_source(link_id, shared_by_user_id=user_id, platform="telegram")

            # Enhanced confirmation with validation details
            success_summary = ai_analysis.get("summary") if ai_analysis else (user_note or metadata.get("description") or "Saved successfully.")
            
            # Create detailed confirmation message
            confirmation_parts = []
            if user_note:
                confirmation_parts.append(f"✅ **Saved with your context:** {user_note}")
            
            confirmation_parts.extend([
                f"📄 **Content analyzed:** {len(text_content.split()) if text_content else 0} words processed",
                f"🏷️ **Categories:** {', '.join(categories[:3]) if categories else 'General'}"
            ])
            
            if entities:
                entity_names = [e.get('name', 'Unknown') for e in entities[:3]]
                confirmation_parts.append(f"🔍 **Key entities:** {', '.join(entity_names)}")
            
            confirmation_message = "\n".join(confirmation_parts)
            
            results.append(
                {
                    "status": "ok",
                    "title": metadata.get("title") or resolved_url,
                    "url": resolved_url,
                    "summary": success_summary,
                    "categories": categories,
                    "warning": warning,
                    "extraction_method": extraction_method,
                    "confirmation": confirmation_message,
                    "entities_count": len(entities) if entities else 0,
                    "user_context_used": bool(user_note),
                }
            )
        except Exception as exc:  # noqa: broad-except -- we need to report the failure to the user.
            logger.exception("Error processing link %s", url)
            results.append({"status": "error", "message": f"⚠️ Error saving {url}: {exc}"})

    message_blocks = []
    for result in results:
        if result["status"] == "ok":
            # Show the link entry
            message_blocks.append(
                _render_link_entry(
                    {
                        "title": result["title"],
                        "url": result["url"],
                        "ai_summary": result["summary"],
                        "categories": result["categories"],
                    }
                )
            )
            
            # Add confirmation details
            if result.get("confirmation"):
                message_blocks.append(f"<i>{escape(result['confirmation'])}</i>")
            
            # Encourage adding context if user didn't provide any
            if not result.get("user_context_used"):
                message_blocks.append(
                    "💡 <i>Tip: Next time add context like 'This is about...' or 'I need this for...' "
                    "to make finding it easier!</i>"
                )
            
            # Add method and warning info
            if result.get("extraction_method") == "renderer" and not result.get("warning"):
                message_blocks.append("🔄 <i>Rendered the page in a headless browser to capture the contents.</i>")
            if result.get("warning"):
                message_blocks.append(f"⚠️ {escape(result['warning'])}")
                
        elif result["status"] == "saved_context_only":
            message_blocks.append(escape(result["message"]))
        else:
            message_blocks.append(escape(result["message"]))

    await update.message.reply_text(
        "\n\n".join(message_blocks),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def handle_natural_language_query(update: Update, user_id: int, query: str):
    """Handle free-text queries by searching the user's saved links."""
    if not query:
        await update.message.reply_text("Tell me what you're looking for or send me a link to save.")
        return

    results = find_links_by_query(user_id, query, limit=5)
    if not results:
        await update.message.reply_text(
            "I didn't find anything for that. You can try mentioning a person, topic, or time range."
        )
        return

    header = f"<b>Here is what I found for:</b> {escape(query)}"
    body = "\n\n".join(_render_link_entry(link) for link in results)
    await update.message.reply_text(f"{header}\n\n{body}", parse_mode=ParseMode.HTML, disable_web_page_preview=True)


def _render_link_entry(link: Dict[str, Any]) -> str:
    """Formats a link preview for HTML delivery."""
    title = escape(link.get("title") or link.get("url") or "Untitled")
    url = escape(link.get("url") or "")
    summary = escape(
        link.get("ai_summary")
        or link.get("summary")
        or link.get("description")
        or "Saved."
    )
    categories = ", ".join(link.get("categories") or [])
    categories_html = f"<i>Tags:</i> {escape(categories)}" if categories else ""

    parts = [f"• <a href=\"{url}\">{title}</a>", summary]
    if categories_html:
        parts.append(categories_html)
    return "\n".join(parts)


def _extract_user_note(message_text: str) -> str:
    """Extracts and enriches user-provided context from the message by removing URLs."""
    if not message_text:
        return ""
    
    # Remove URLs but preserve the surrounding context
    cleaned = URL_PATTERN.sub(" ", message_text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    # If the user provided substantial context, preserve it completely
    if len(cleaned.split()) >= 3:
        return cleaned
    
    return cleaned
