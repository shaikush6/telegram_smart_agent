"""
link_retriever.py - Natural language search for links.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import database

STOP_WORDS = {
    "the",
    "and",
    "about",
    "please",
    "show",
    "find",
    "me",
    "for",
    "that",
    "this",
    "what",
    "was",
    "were",
    "is",
    "are",
    "be",
    "a",
    "an",
    "to",
    "on",
    "in",
}

TEMPORAL_TOKENS = {
    "today",
    "yesterday",
    "tonight",
    "week",
    "month",
    "year",
    "recent",
    "latest",
    "last",
}


def find_links_by_query(user_id: int, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Finds links based on a natural language query with enhanced context matching.
    """
    query = query.strip()
    if not query:
        return []

    query_lower = query.lower()

    # Handle recent/latest queries
    if any(token in query_lower for token in ("recent", "latest")):
        return database.get_recent_links(user_id, limit=limit)

    # Extract time filters and entities
    window_start = _extract_time_filter(query_lower)
    entities = _extract_entities(query)
    
    # Enhanced search strategy: try multiple approaches
    search_results = []
    
    # 1. First try: search with original query (captures user context and rich descriptions)
    results1 = database.search_links(user_id, query, limit=limit * 2)
    search_results.extend(results1)
    
    # 2. Second try: search with cleaned terms + entities
    cleaned_terms = _clean_query_terms(query)
    if cleaned_terms and cleaned_terms != query:
        search_terms = cleaned_terms
        if entities:
            search_terms = f"{search_terms} {' '.join(entities)}".strip()
        
        results2 = database.search_links(user_id, search_terms, limit=limit * 2)
        # Add unique results not already found
        existing_urls = {r.get('url') for r in search_results}
        search_results.extend([r for r in results2 if r.get('url') not in existing_urls])
    
    # 3. Third try: search by individual meaningful words (for partial matches)
    meaningful_words = _extract_meaningful_words(query)
    if meaningful_words and len(meaningful_words) >= 2:
        for word in meaningful_words[:3]:  # Try top 3 meaningful words
            if len(word) >= 4:  # Only search for substantial words
                word_results = database.search_links(user_id, word, limit=5)
                existing_urls = {r.get('url') for r in search_results}
                search_results.extend([r for r in word_results if r.get('url') not in existing_urls])
    
    # Apply time filtering if specified
    if window_start:
        search_results = [
            link
            for link in search_results
            if link.get("created_at") and link["created_at"] >= window_start
        ]
    
    # Score and rank results by relevance
    scored_results = _score_search_results(search_results, query, entities)
    
    return scored_results[:limit]


def _clean_query_terms(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9']+", query.lower())
    filtered = [
        token
        for token in tokens
        if token not in STOP_WORDS and token not in TEMPORAL_TOKENS
    ]
    return " ".join(filtered)


def _extract_entities(query: str) -> List[str]:
    matches = re.findall(
        r"(?:from|by|with|shared by)\s+([A-Za-z0-9][A-Za-z0-9_\-]*)",
        query,
        flags=re.IGNORECASE,
    )
    # Keep original casing for better search hits.
    return matches


def _extract_time_filter(query_lower: str) -> Optional[datetime]:
    now = datetime.now(timezone.utc)

    if "today" in query_lower:
        return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    if "yesterday" in query_lower:
        midnight_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        return midnight_today - timedelta(days=1)

    if "last week" in query_lower:
        return now - timedelta(days=7)

    if "last month" in query_lower:
        return now - timedelta(days=30)

    if "last year" in query_lower:
        return now - timedelta(days=365)

    match_days = re.search(r"last (\d+) days", query_lower)
    if match_days:
        days = int(match_days.group(1))
        return now - timedelta(days=days)

    match_weeks = re.search(r"last (\d+) weeks", query_lower)
    if match_weeks:
        weeks = int(match_weeks.group(1))
        return now - timedelta(weeks=weeks)

    return None


def _extract_meaningful_words(query: str) -> List[str]:
    """Extract meaningful words from query, ranked by potential search value."""
    tokens = re.findall(r"[A-Za-z0-9']+", query.lower())
    
    # Filter out stop words and temporal tokens
    meaningful = [
        token for token in tokens
        if token not in STOP_WORDS 
        and token not in TEMPORAL_TOKENS
        and len(token) >= 3  # Only substantial words
    ]
    
    # Prioritize longer words and technical terms
    meaningful.sort(key=lambda x: (-len(x), x))
    
    return meaningful


def _score_search_results(results: List[Dict[str, Any]], query: str, entities: List[str]) -> List[Dict[str, Any]]:
    """Score and rank search results by relevance to query."""
    if not results:
        return []
    
    query_lower = query.lower()
    query_words = set(re.findall(r"[A-Za-z0-9']+", query_lower))
    
    scored_results = []
    for result in results:
        score = 0
        
        # Check title matches
        title = (result.get("title") or "").lower()
        if title:
            title_words = set(re.findall(r"[A-Za-z0-9']+", title))
            score += len(query_words.intersection(title_words)) * 3
        
        # Check summary/description matches  
        summary = (result.get("ai_summary") or result.get("description") or "").lower()
        if summary:
            summary_words = set(re.findall(r"[A-Za-z0-9']+", summary))
            score += len(query_words.intersection(summary_words)) * 2
        
        # Check category matches
        categories = result.get("categories") or []
        category_text = " ".join(categories).lower()
        if category_text:
            category_words = set(re.findall(r"[A-Za-z0-9']+", category_text))
            score += len(query_words.intersection(category_words)) * 2
        
        # Bonus for entity matches
        if entities:
            for entity in entities:
                entity_lower = entity.lower()
                if entity_lower in title or entity_lower in summary:
                    score += 5
        
        # Exact phrase matches get highest score
        if query_lower in title or query_lower in summary:
            score += 10
        
        scored_results.append((score, result))
    
    # Sort by score (descending) and return results
    scored_results.sort(key=lambda x: -x[0])
    return [result for score, result in scored_results]
