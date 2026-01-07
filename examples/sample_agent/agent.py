#!/usr/bin/env python3
"""Sample RAG-based customer service agent for TechGear.

This agent uses LiteLLM for generation and simple keyword-based retrieval
to answer questions based on the knowledge base.

Usage:
    echo "What is your return policy?" | python agent.py
    python agent.py "What is your return policy?"
    python agent.py --json '{"message": "What is your return policy?"}'
"""

import json
import os
import sys
from pathlib import Path


def load_knowledge_base(kb_path: Path) -> dict[str, str]:
    """Load all documents from the knowledge base."""
    docs = {}

    for file_path in kb_path.rglob("*.md"):
        rel_path = file_path.relative_to(kb_path)
        content = file_path.read_text(encoding="utf-8")
        docs[str(rel_path)] = content

    return docs


def find_relevant_docs(query: str, docs: dict[str, str], top_k: int = 3) -> list[tuple[str, str]]:
    """Find relevant documents using keyword matching.

    In a production system, this would use embeddings and vector search.
    """
    query_lower = query.lower()
    scores = []

    # Keywords to look for
    keywords = query_lower.split()

    for path, content in docs.items():
        content_lower = content.lower()
        score = 0

        # Score based on keyword matches
        for word in keywords:
            if len(word) > 3:  # Skip short words
                score += content_lower.count(word)

        # Boost based on path relevance
        if "return" in query_lower and "return" in path.lower():
            score += 10
        if "ship" in query_lower and "ship" in path.lower():
            score += 10
        if "warranty" in query_lower and "warranty" in path.lower():
            score += 10
        if "faq" in path.lower():
            score += 2  # FAQ is generally relevant

        scores.append((score, path, content))

    # Sort by score and return top_k
    scores.sort(reverse=True, key=lambda x: x[0])
    return [(path, content) for score, path, content in scores[:top_k] if score > 0]


def generate_response(query: str, context: str) -> dict:
    """Generate a response using LLM."""
    try:
        import litellm

        prompt = f"""You are a helpful customer service agent for TechGear, an electronics retailer.
Answer the customer's question based on the provided knowledge base context.
Be friendly, accurate, and concise. If the information isn't in the context, say so politely.

KNOWLEDGE BASE CONTEXT:
{context[:3000]}

CUSTOMER QUESTION: {query}

Provide a helpful response:"""

        response = litellm.completion(
            model=os.environ.get("AGENT_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )

        text = response.choices[0].message.content or ""

        return {
            "response": text,
            "citations": [],  # Would extract from context in production
            "confidence": 0.9,
        }

    except Exception as e:
        # Fallback to template-based response if LLM fails
        return generate_template_response(query, context)


def generate_template_response(query: str, context: str) -> dict:
    """Generate a template-based response without LLM.

    This is a fallback for when LLM is not available.
    """
    query_lower = query.lower()

    # Simple pattern matching for common questions
    if "return policy" in query_lower or "return" in query_lower:
        return {
            "response": "TechGear offers a 30-day return policy for most products. "
            "Items must be returned in original packaging with all accessories. "
            "Refunds are processed within 5-7 business days after we receive the item. "
            "Some items like opened headphones have a 15-day return window.",
            "citations": ["policies/returns.md"],
            "confidence": 0.8,
        }

    if "shipping" in query_lower or "delivery" in query_lower:
        return {
            "response": "We offer free standard shipping on orders over $50 (5-7 business days). "
            "Express shipping is $12.99 (2-3 days) and next-day shipping is $24.99. "
            "We also ship internationally to Canada, UK, and select European countries.",
            "citations": ["policies/shipping.md"],
            "confidence": 0.8,
        }

    if "warranty" in query_lower:
        return {
            "response": "Most TechGear products come with a 1-year manufacturer warranty. "
            "Smart home devices have 2-year warranties, and accessories have 90-day coverage. "
            "We also offer TechGear Protection Plans starting at $49.99/year for extended coverage.",
            "citations": ["policies/warranty.md"],
            "confidence": 0.8,
        }

    if "payment" in query_lower or "pay" in query_lower:
        return {
            "response": "We accept all major credit cards (Visa, MasterCard, AmEx, Discover), "
            "PayPal, Apple Pay, Google Pay, and TechGear Gift Cards. "
            "For orders over $200, financing through Affirm is available.",
            "citations": ["company-info.md"],
            "confidence": 0.8,
        }

    if "contact" in query_lower or "support" in query_lower or "hours" in query_lower:
        return {
            "response": "You can reach TechGear support at support@techgear.example.com or "
            "call 1-800-TECHGEAR (1-800-832-4432). Our hours are Monday-Friday 9 AM - 6 PM EST, "
            "and Saturday 10 AM - 4 PM EST (chat only).",
            "citations": ["company-info.md"],
            "confidence": 0.8,
        }

    # Generic fallback
    return {
        "response": "I'd be happy to help you with that! For the most accurate information, "
        "please visit our website at techgear.example.com or contact our support team at "
        "1-800-TECHGEAR. Is there anything specific you'd like to know?",
        "citations": [],
        "confidence": 0.5,
    }


def main():
    """Main entry point."""
    # Determine knowledge base path
    script_dir = Path(__file__).parent
    kb_path = script_dir.parent / "knowledge-base"

    if not kb_path.exists():
        kb_path = Path("examples/knowledge-base")

    # Load knowledge base
    docs = load_knowledge_base(kb_path) if kb_path.exists() else {}

    # Get input
    if len(sys.argv) > 1:
        if sys.argv[1] == "--json":
            # JSON mode
            data = json.loads(sys.argv[2])
            query = data.get("message", "")
        else:
            # Argument mode
            query = sys.argv[1]
    else:
        # Pipe mode - read from stdin
        query = sys.stdin.read().strip()

    if not query:
        print("Error: No message provided", file=sys.stderr)
        sys.exit(1)

    # Find relevant documents
    relevant_docs = find_relevant_docs(query, docs)
    context = "\n\n".join(f"[{path}]\n{content}" for path, content in relevant_docs)

    # Generate response
    result = generate_response(query, context)

    # Output based on mode
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(json.dumps(result))
    else:
        print(result["response"])


if __name__ == "__main__":
    main()

