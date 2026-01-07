"""Knowledge base data models."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Document:
    """A single document in the knowledge base."""

    path: Path
    content: str
    title: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def filename(self) -> str:
        """Get the filename without extension."""
        return self.path.stem

    @property
    def extension(self) -> str:
        """Get the file extension."""
        return self.path.suffix.lower()

    def __repr__(self) -> str:
        return f"Document(path={self.path}, title={self.title}, len={len(self.content)})"


@dataclass
class KnowledgeBase:
    """A collection of documents forming a knowledge base."""

    path: Path
    documents: list[Document] = field(default_factory=list)

    @property
    def total_words(self) -> int:
        """Total word count across all documents."""
        return sum(len(doc.content.split()) for doc in self.documents)

    @property
    def document_count(self) -> int:
        """Number of documents."""
        return len(self.documents)

    def get_document(self, path: str) -> Optional[Document]:
        """Get a document by its relative path."""
        for doc in self.documents:
            if str(doc.path).endswith(path):
                return doc
        return None

    def __repr__(self) -> str:
        return f"KnowledgeBase(path={self.path}, docs={self.document_count})"

