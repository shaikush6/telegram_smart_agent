# tools/knowledge_base.py - Local knowledge base for your files

import os
import json
import asyncio
from typing import List, Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    Simple knowledge base for storing and retrieving information from your files
    Will be expanded to support vector search later
    """

    def __init__(self, config):
        self.config = config
        self.kb_path = os.path.join(config.KNOWLEDGE_BASE_DIR, "knowledge.json")
        self.documents = self._load_knowledge_base()

    def _load_knowledge_base(self) -> Dict:
        """Load existing knowledge base or create new one"""
        if os.path.exists(self.kb_path):
            try:
                with open(self.kb_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading knowledge base: {e}")
                return {"documents": [], "metadata": {"created": datetime.now().isoformat()}}
        else:
            return {"documents": [], "metadata": {"created": datetime.now().isoformat()}}

    def _save_knowledge_base(self):
        """Save knowledge base to disk"""
        try:
            self.documents["metadata"]["last_updated"] = datetime.now().isoformat()
            with open(self.kb_path, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving knowledge base: {e}")

    async def add_document(self, title: str, content: str, doc_type: str = "text",
                           metadata: Optional[Dict] = None) -> str:
        """Add a document to the knowledge base"""
        try:
            doc_id = f"doc_{len(self.documents['documents'])}_{int(datetime.now().timestamp())}"

            document = {
                "id": doc_id,
                "title": title,
                "content": content,
                "type": doc_type,
                "added_date": datetime.now().isoformat(),
                "metadata": metadata or {}
            }

            self.documents["documents"].append(document)
            self._save_knowledge_base()

            return f"✅ Added document '{title}' to knowledge base (ID: {doc_id})"

        except Exception as e:
            logger.error(f"Error adding document: {e}")
            return f"❌ Error adding document: {str(e)}"

    async def search_documents(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Simple text search in documents
        In a full implementation, this would use vector similarity
        """
        try:
            query_lower = query.lower()
            matching_docs = []

            for doc in self.documents["documents"]:
                title_match = query_lower in doc["title"].lower()
                content_match = query_lower in doc["content"].lower()

                if title_match or content_match:
                    # Simple scoring (better matches first)
                    score = 0
                    if title_match:
                        score += 2
                    if content_match:
                        score += 1

                    matching_docs.append({
                        "document": doc,
                        "score": score
                    })

            # Sort by score and return top results
            matching_docs.sort(key=lambda x: x["score"], reverse=True)
            return [match["document"] for match in matching_docs[:limit]]

        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []

    async def get_document(self, doc_id: str) -> Optional[Dict]:
        """Get a specific document by ID"""
        for doc in self.documents["documents"]:
            if doc["id"] == doc_id:
                return doc
        return None

    async def list_documents(self) -> List[Dict]:
        """List all documents in the knowledge base"""
        return [{
            "id": doc["id"],
            "title": doc["title"],
            "type": doc["type"],
            "added_date": doc["added_date"]
        } for doc in self.documents["documents"]]

    async def delete_document(self, doc_id: str) -> str:
        """Delete a document from the knowledge base"""
        try:
            original_count = len(self.documents["documents"])
            self.documents["documents"] = [
                doc for doc in self.documents["documents"]
                if doc["id"] != doc_id
            ]

            if len(self.documents["documents"]) < original_count:
                self._save_knowledge_base()
                return f"✅ Deleted document {doc_id}"
            else:
                return f"❌ Document {doc_id} not found"

        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return f"❌ Error deleting document: {str(e)}"

    def get_stats(self) -> Dict:
        """Get knowledge base statistics"""
        docs = self.documents["documents"]

        stats = {
            "total_documents": len(docs),
            "document_types": {},
            "total_content_length": 0,
            "created": self.documents["metadata"].get("created", "Unknown"),
            "last_updated": self.documents["metadata"].get("last_updated", "Never")
        }

        for doc in docs:
            doc_type = doc.get("type", "unknown")
            stats["document_types"][doc_type] = stats["document_types"].get(doc_type, 0) + 1
            stats["total_content_length"] += len(doc.get("content", ""))

        return stats