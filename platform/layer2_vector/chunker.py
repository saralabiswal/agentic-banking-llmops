"""Hierarchical policy chunking for Layer 2 retrieval.

Author: Sarala Biswal
"""

from __future__ import annotations

from collections.abc import Mapping
from platform.core.exceptions import SchemaValidationError
from platform.core.schemas import PolicyChunk
from typing import Any, Literal, cast

DocumentType = Literal["POLICY", "REGULATION", "PLAYBOOK", "COMPLIANCE"]


class HierarchicalChunker:
    """Splits policy YAML documents into document, section, and paragraph chunks."""

    def chunk(self, document: Mapping[str, Any]) -> list[PolicyChunk]:
        """Return hierarchical chunks with parent references and policy metadata."""
        document_id = _required_text(document, "document_id")
        title = _required_text(document, "title")
        document_type = _document_type(_required_text(document, "document_type"))
        product_line = _required_text(document, "product_line")
        jurisdiction = _required_text(document, "jurisdiction")
        version = _required_text(document, "version")
        content = _as_mapping(document.get("content"), "content")
        summary = _optional_text(content.get("summary"))

        chunks: list[PolicyChunk] = []
        document_chunk_id = f"{document_id}-{version}-DOCUMENT-0"
        if summary:
            chunks.append(
                _make_chunk(
                    chunk_id=document_chunk_id,
                    document_id=document_id,
                    title=title,
                    document_type=document_type,
                    version=version,
                    raw_text=f"{title}. {summary}",
                    chunk_type="DOCUMENT",
                    parent_chunk_id=None,
                    product_line=product_line,
                    jurisdiction=jurisdiction,
                )
            )

        paragraph_index = 1
        for section_index, section in enumerate(_sections(content), start=1):
            section_title = _optional_text(section.get("title")) or f"Section {section_index}"
            section_content = _optional_text(section.get("content"))
            paragraph_texts = [
                paragraph for paragraph in _paragraphs(section.get("paragraphs")) if paragraph
            ]
            section_chunk_id = f"{document_id}-{version}-SECTION-{section_index}"
            section_raw_text = _join_text([section_title, section_content, *paragraph_texts])
            chunks.append(
                _make_chunk(
                    chunk_id=section_chunk_id,
                    document_id=document_id,
                    title=title,
                    document_type=document_type,
                    version=version,
                    raw_text=section_raw_text,
                    chunk_type="SECTION",
                    parent_chunk_id=document_chunk_id if summary else None,
                    product_line=product_line,
                    jurisdiction=jurisdiction,
                )
            )

            for paragraph in paragraph_texts:
                paragraph_chunk_id = f"{document_id}-{version}-PARAGRAPH-{paragraph_index}"
                chunks.append(
                    _make_chunk(
                        chunk_id=paragraph_chunk_id,
                        document_id=document_id,
                        title=title,
                        document_type=document_type,
                        version=version,
                        raw_text=f"{section_title}. {paragraph}",
                        chunk_type="PARAGRAPH",
                        parent_chunk_id=section_chunk_id,
                        product_line=product_line,
                        jurisdiction=jurisdiction,
                    )
                )
                paragraph_index += 1

        return chunks


def _make_chunk(
    *,
    chunk_id: str,
    document_id: str,
    title: str,
    document_type: DocumentType,
    version: str,
    raw_text: str,
    chunk_type: Literal["DOCUMENT", "SECTION", "PARAGRAPH"],
    parent_chunk_id: str | None,
    product_line: str,
    jurisdiction: str,
) -> PolicyChunk:
    return PolicyChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        document_title=title,
        document_type=document_type,
        doc_version=version,
        raw_text=raw_text,
        rerank_score=0.0,
        chunk_type=chunk_type,
        parent_chunk_id=parent_chunk_id,
        product_line=product_line,
        jurisdiction=jurisdiction,
    )


def _required_text(document: Mapping[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        message = f"Knowledge base document missing required text field: {key}"
        raise SchemaValidationError(message)
    return value.strip()


def _optional_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_mapping(value: object, key: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        message = f"Knowledge base document field must be a mapping: {key}"
        raise SchemaValidationError(message)
    return cast("Mapping[str, Any]", value)


def _sections(content: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sections = content.get("sections")
    if not isinstance(sections, list):
        return []
    return [
        cast("Mapping[str, Any]", section)
        for section in sections
        if isinstance(section, Mapping)
    ]


def _paragraphs(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _document_type(value: str) -> DocumentType:
    allowed: set[str] = {"POLICY", "REGULATION", "PLAYBOOK", "COMPLIANCE"}
    normalized = value.upper()
    if normalized not in allowed:
        message = f"Unsupported document_type: {value}"
        raise SchemaValidationError(message)
    return cast("DocumentType", normalized)


def _join_text(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())
