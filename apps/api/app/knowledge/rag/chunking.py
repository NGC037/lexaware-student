"""Deterministic, section-aware chunking for governed knowledge versions."""

import hashlib
import uuid
from dataclasses import dataclass

from app.knowledge.rag.config import RetrievalConfig

_CHUNK_NAMESPACE = uuid.UUID("5ff5a3c6-e4c4-53c4-837c-075f74f17dbd")


@dataclass(frozen=True, slots=True)
class KnowledgeSection:
    key: str
    title: str
    text: str


@dataclass(frozen=True, slots=True)
class KnowledgeChunkData:
    chunk_id: uuid.UUID
    section_key: str
    section_title: str
    ordinal: int
    text: str
    content_hash: str
    chunking_version: str


def split_section(text: str, *, size: int, overlap: int) -> list[str]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Chunk size must be positive and overlap smaller than size.")
    content = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not content:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = min(start + size, len(content))
        if end < len(content):
            boundary = content.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        part = content[start:end].strip()
        if part:
            chunks.append(part)
        if end >= len(content):
            break
        start = max(start + 1, end - overlap)
    return chunks


def chunk_sections(
    version_id: uuid.UUID,
    sections: list[KnowledgeSection],
    config: RetrievalConfig | None = None,
) -> list[KnowledgeChunkData]:
    selected = config or RetrievalConfig()
    result: list[KnowledgeChunkData] = []
    for section in sections:
        prefix = f"Section: {section.title}\n"
        for ordinal, part in enumerate(
            split_section(section.text, size=selected.chunk_size, overlap=selected.chunk_overlap)
        ):
            body = prefix + part
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            stable_name = (
                f"{version_id}:{selected.chunking_version}:{section.key}:{ordinal}:{digest}"
            )
            result.append(
                KnowledgeChunkData(
                    chunk_id=uuid.uuid5(_CHUNK_NAMESPACE, stable_name),
                    section_key=section.key,
                    section_title=section.title,
                    ordinal=ordinal,
                    text=body,
                    content_hash=digest,
                    chunking_version=selected.chunking_version,
                )
            )
    return result
