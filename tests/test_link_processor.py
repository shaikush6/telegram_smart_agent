import base64
import math
from pathlib import Path
from types import SimpleNamespace

import link_processor
from link_processor import extract_metadata, extract_text_content


SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <title>Example Article</title>
    <meta name="description" content="A sample description." />
    <meta property="og:description" content="OG description takes precedence." />
    <meta name="author" content="Jane Doe" />
    <meta property="article:published_time" content="2024-01-10T12:00:00Z" />
    <link rel="icon" href="/favicon.ico" />
    <link rel="canonical" href="https://example.com/articles/sample" />
  </head>
  <body>
    <header>This header should be ignored.</header>
    <article>
      <h1>Example Article</h1>
      <p>This is the first paragraph.</p>
      <p>This is the second paragraph with <strong>bold</strong> text.</p>
    </article>
    <script>console.log("remove me");</script>
  </body>
</html>
"""


def test_extract_metadata_prioritises_opengraph_description():
    metadata = extract_metadata(
        SAMPLE_HTML,
        url="https://example.com/articles/sample?ref=newsletter",
        content_type="text/html",
    )

    assert metadata["title"] == "Example Article"
    assert metadata["description"] == "OG description takes precedence."
    assert metadata["author"] == "Jane Doe"
    assert metadata["publish_date"] == "2024-01-10T12:00:00Z"
    assert metadata["favicon"] == "https://example.com/favicon.ico"
    assert metadata["canonical_url"] == "https://example.com/articles/sample"
    assert metadata["language"] == "en"
    assert metadata["domain"] == "example.com"
    assert metadata["content_type"] == "text/html"

    # Word count should be approximated from cleaned text (2 sentences -> 16 words)
    assert metadata["word_count"] >= 10
    assert metadata["read_time"] == math.ceil(metadata["word_count"] / 200)


def test_extract_text_content_strips_scripts_and_whitespace():
    text = extract_text_content(SAMPLE_HTML)
    assert "console.log" not in text
    assert "This header should be ignored" not in text
    assert "This is the first paragraph." in text
    assert "This is the second paragraph with bold text." in text


def test_process_url_uses_renderer_for_sparse_pages(monkeypatch, tmp_path):
    minimal_page = {
        "html": "<html><head><title>Minimal</title></head><body></body></html>",
        "content_type": "text/html",
        "final_url": "https://example.com/paywall",
    }
    monkeypatch.setattr(link_processor, "fetch_page_content", lambda url: minimal_page)

    render_output = SimpleNamespace(
        html="<html><body><p>Rendered content available.</p></body></html>",
        text_content="Rendered content available.",
        resolved_url="https://example.com/paywall?auth=true",
        screenshot_base64=None,
        screenshot_mime="image/png",
        status="rendered",
    )
    monkeypatch.setattr(link_processor, "render_with_browser", lambda url: render_output)
    monkeypatch.setattr(link_processor, "extract_text_from_image", lambda *args, **kwargs: "")

    monkeypatch.setattr(link_processor.config, "ENABLE_RENDERER", True, raising=False)
    monkeypatch.setattr(link_processor.config, "RENDERER_URL", "https://renderer.local", raising=False)
    monkeypatch.setattr(link_processor.config, "RENDERER_MIN_WORDS", 50, raising=False)
    monkeypatch.setattr(link_processor, "SCREENSHOT_DIR", tmp_path / "screenshots")
    link_processor.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    result = link_processor.process_url("https://example.com/paywall")

    assert result["extraction_method"] == "renderer"
    assert result["text_content"] == "Rendered content available."
    assert result["resolved_url"].endswith("auth=true")
    assert result["metadata"]["word_count"] == len("Rendered content available.".split())


def test_process_url_uses_ocr_when_renderer_only_returns_screenshot(monkeypatch, tmp_path):
    minimal_page = {
        "html": "<html><head><title>Empty</title></head><body></body></html>",
        "content_type": "text/html",
        "final_url": "https://example.com/image-only",
    }
    monkeypatch.setattr(link_processor, "fetch_page_content", lambda url: minimal_page)

    fake_image_bytes = b"pretend this is a png"
    screenshot_base64 = base64.b64encode(fake_image_bytes).decode("ascii")
    render_output = SimpleNamespace(
        html="",
        text_content="",
        resolved_url="https://example.com/image-only",
        screenshot_base64=screenshot_base64,
        screenshot_mime="image/png",
        status="rendered",
    )
    monkeypatch.setattr(link_processor, "render_with_browser", lambda url: render_output)
    monkeypatch.setattr(
        link_processor,
        "extract_text_from_image",
        lambda *args, **kwargs: "Text derived from OCR.",
    )

    monkeypatch.setattr(link_processor.config, "ENABLE_RENDERER", True, raising=False)
    monkeypatch.setattr(link_processor.config, "RENDERER_URL", "https://renderer.local", raising=False)
    monkeypatch.setattr(link_processor.config, "RENDERER_MIN_WORDS", 50, raising=False)
    monkeypatch.setattr(link_processor.config, "ENABLE_SCREENSHOT_OCR", True, raising=False)
    monkeypatch.setattr(link_processor, "SCREENSHOT_DIR", tmp_path / "screenshots")
    link_processor.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    result = link_processor.process_url("https://example.com/image-only")

    assert result["extraction_method"] == "renderer"
    assert result["text_content"] == "Text derived from OCR."
    assert result["screenshot_path"]
    assert Path(result["screenshot_path"]).exists()

    # Clean up the saved screenshot after assertion.
    Path(result["screenshot_path"]).unlink()
