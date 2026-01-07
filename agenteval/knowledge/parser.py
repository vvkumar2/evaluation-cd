"""Knowledge base document parser."""

import re
from pathlib import Path
from typing import Optional

import frontmatter

from agenteval.models.knowledge import Document, KnowledgeBase


class KnowledgeBaseParser:
    """Parse documents from a knowledge base directory."""

    SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".text"}

    def parse(self, path: Path) -> KnowledgeBase:
        """Parse all documents in a directory."""
        if not path.exists():
            raise FileNotFoundError(f"Knowledge base path not found: {path}")

        if not path.is_dir():
            raise ValueError(f"Expected directory, got file: {path}")

        documents = []
        for file_path in self._find_documents(path):
            doc = self._parse_document(file_path, path)
            if doc:
                documents.append(doc)

        return KnowledgeBase(path=path, documents=documents)

    def _find_documents(self, path: Path) -> list[Path]:
        """Find all supported documents in the directory."""
        documents = []
        for ext in self.SUPPORTED_EXTENSIONS:
            documents.extend(path.rglob(f"*{ext}"))
        return sorted(documents)

    def _parse_document(self, file_path: Path, base_path: Path) -> Optional[Document]:
        """Parse a single document."""
        try:
            content = file_path.read_text(encoding="utf-8")

            # Try to parse frontmatter if it's a markdown file
            title = None
            metadata = {}

            if file_path.suffix.lower() in {".md", ".markdown"}:
                try:
                    post = frontmatter.loads(content)
                    content = post.content
                    metadata = dict(post.metadata)
                    title = metadata.pop("title", None)
                except Exception:
                    pass  # If frontmatter parsing fails, use raw content

            # Extract title from first heading if not in frontmatter
            if not title:
                title = self._extract_title(content)

            # Calculate relative path
            rel_path = file_path.relative_to(base_path)

            return Document(
                path=rel_path,
                content=content.strip(),
                title=title,
                metadata=metadata,
            )

        except Exception as e:
            # Log error but continue parsing other documents
            print(f"Warning: Failed to parse {file_path}: {e}")
            return None

    def _extract_title(self, content: str) -> Optional[str]:
        """Extract title from first markdown heading."""
        # Look for # heading
        match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()

        # Look for underline style heading
        lines = content.split("\n")
        if len(lines) >= 2:
            if re.match(r"^=+$", lines[1].strip()):
                return lines[0].strip()

        return None


class DocumentChunker:
    """Split documents into smaller chunks for indexing."""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        """Initialize chunker.

        Args:
            chunk_size: Target size of each chunk in words.
            overlap: Number of overlapping words between chunks.
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, document: Document) -> list[dict]:
        """Split document into chunks."""
        content = document.content
        sections = self._split_by_sections(content)

        chunks = []
        for section_title, section_content in sections:
            section_chunks = self._chunk_text(section_content)
            for i, chunk_text in enumerate(section_chunks):
                chunks.append({
                    "document_path": str(document.path),
                    "document_title": document.title,
                    "section_title": section_title,
                    "chunk_index": i,
                    "content": chunk_text,
                })

        return chunks

    def _split_by_sections(self, content: str) -> list[tuple[Optional[str], str]]:
        """Split content by markdown sections."""
        # Split by ## headings
        pattern = r"^##\s+(.+)$"
        parts = re.split(pattern, content, flags=re.MULTILINE)

        if len(parts) == 1:
            # No sections found, return whole content
            return [(None, content)]

        sections = []

        # First part before any section
        if parts[0].strip():
            sections.append((None, parts[0].strip()))

        # Pair up section titles with their content
        for i in range(1, len(parts), 2):
            title = parts[i].strip() if i < len(parts) else None
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if content:
                sections.append((title, content))

        return sections

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks of approximately chunk_size words."""
        words = text.split()

        if len(words) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(words):
            end = start + self.chunk_size
            chunk_words = words[start:end]
            chunks.append(" ".join(chunk_words))
            start = end - self.overlap

        return chunks

