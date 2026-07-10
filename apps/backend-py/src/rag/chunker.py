"""
Job Raider - Text Chunker

Chunks job listings and user profiles into pieces suitable for
embedding generation, with configurable strategies and overlap.

Author: Job Raider
Date: 2026-04-26
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from .config import ChunkingConfig


@dataclass
class TextChunk:
    """A chunk of text with metadata for traceability.

    Attributes:
        content: The text content of this chunk.
        chunk_index: Zero-based index of this chunk within its source.
        source_id: Identifier of the source (job_id or profile identifier).
        source_type: Type of source ("job" or "profile").
        section: Section name (e.g., "description", "skills", "summary").
        token_count: Estimated token count of the content.
        metadata: Additional metadata for filtering or display.
    """

    content: str
    chunk_index: int
    source_id: str
    source_type: str
    section: Optional[str] = None
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TextChunker:
    """Chunk text for embedding generation.

    Supports multiple strategies optimized for job descriptions and profiles.
    Each chunk is prefixed with contextual headers to improve embedding quality.

    Attributes:
        config: Chunking configuration parameters.
    """

    def __init__(self, config: Optional[ChunkingConfig] = None):
        """Initialize the text chunker.

        Args:
            config: Chunking configuration. Uses defaults if None.
        """
        self.config = config or ChunkingConfig()

    def chunk_text(
        self,
        text: str,
        source_id: str,
        source_type: str,
        section: Optional[str] = None,
    ) -> List[TextChunk]:
        """Chunk a text string into pieces suitable for embedding.

        Uses the configured strategy (recursive, fixed, or section-based).

        Args:
            text: Full text to chunk.
            source_id: Identifier for the source (job_id or "profile").
            source_type: Type of source ("job" or "profile").
            section: Optional section name for context.

        Returns:
            List of TextChunk objects.
        """
        if not text or not text.strip():
            return []

        # Short text fits in a single chunk
        estimated_tokens = self._estimate_tokens(text)
        if estimated_tokens <= self.config.max_chunk_size:
            return [
                TextChunk(
                    content=text.strip(),
                    chunk_index=0,
                    source_id=source_id,
                    source_type=source_type,
                    section=section,
                    token_count=estimated_tokens,
                )
            ]

        # Apply chunking strategy
        if self.config.strategy == "recursive":
            pieces = self._chunk_recursive(
                text, self.config.max_chunk_size, self.config.overlap
            )
        elif self.config.strategy == "fixed":
            pieces = self._chunk_fixed(text, self.config.max_chunk_size)
        else:
            pieces = self._chunk_recursive(
                text, self.config.max_chunk_size, self.config.overlap
            )

        return [
            TextChunk(
                content=piece.strip(),
                chunk_index=i,
                source_id=source_id,
                source_type=source_type,
                section=section,
                token_count=self._estimate_tokens(piece),
            )
            for i, piece in enumerate(pieces)
            if piece.strip()
        ]

    def chunk_job(self, job: JobListing) -> List[TextChunk]:
        """Chunk a JobListing into embedding-ready pieces.

        Produces contextual chunks from the title/company, description,
        requirements, skills, and metadata. Each chunk is prefixed with
        context like "Job Title: X, Company: Y" to ground the embedding.

        Args:
            job: JobListing to chunk.

        Returns:
            List of TextChunk objects.
        """
        chunks: List[TextChunk] = []
        context_prefix = f"Job Title: {job.title}, Company: {job.company}"
        if job.location:
            context_prefix += f", Location: {job.location}"
        if job.experience_level and job.experience_level != "Not Specified":
            context_prefix += f", Level: {job.experience_level}"

        # Title + company (always fits in one chunk)
        chunks.append(
            TextChunk(
                content=context_prefix,
                chunk_index=0,
                source_id=job.job_id,
                source_type="job",
                section="header",
                token_count=self._estimate_tokens(context_prefix),
            )
        )

        # Description
        if job.description:
            desc_text = f"{context_prefix}\n\nDescription: {job.description}"
            desc_chunks = self.chunk_text(desc_text, job.job_id, "job", "description")
            for c in desc_chunks:
                c.chunk_index = len(chunks)
                chunks.append(c)

        # Requirements
        if job.requirements:
            req_text = "\n".join(f"- {r.text}" for r in job.requirements)
            req_full = f"{context_prefix}\n\nRequirements:\n{req_text}"
            req_chunks = self.chunk_text(req_full, job.job_id, "job", "requirements")
            for c in req_chunks:
                c.chunk_index = len(chunks)
                chunks.append(c)

        # Skills
        if job.skills:
            skill_names = [s.name for s in job.skills]
            skill_text = (
                f"{context_prefix}\n\nRequired Skills: {', '.join(skill_names)}"
            )
            chunks.append(
                TextChunk(
                    content=skill_text,
                    chunk_index=len(chunks),
                    source_id=job.job_id,
                    source_type="job",
                    section="skills",
                    token_count=self._estimate_tokens(skill_text),
                )
            )

        # Responsibilities
        if job.responsibilities:
            resp_text = "\n".join(f"- {r.text}" for r in job.responsibilities)
            resp_full = f"{context_prefix}\n\nResponsibilities:\n{resp_text}"
            resp_chunks = self.chunk_text(
                resp_full, job.job_id, "job", "responsibilities"
            )
            for c in resp_chunks:
                c.chunk_index = len(chunks)
                chunks.append(c)

        return chunks

    def chunk_profile(self, profile: UserProfile) -> List[TextChunk]:
        """Chunk a UserProfile into embedding-ready pieces.

        Produces chunks from the summary, skills, experience entries,
        projects, and education. Each chunk is prefixed with section context.

        Args:
            profile: UserProfile to chunk.

        Returns:
            List of TextChunk objects.
        """
        chunks: List[TextChunk] = []
        source_id = "default_profile"

        # Summary
        if profile.summary:
            summary_text = f"Professional Summary: {profile.summary}"
            chunks.append(
                TextChunk(
                    content=summary_text,
                    chunk_index=len(chunks),
                    source_id=source_id,
                    source_type="profile",
                    section="summary",
                    token_count=self._estimate_tokens(summary_text),
                )
            )

        # Skills grouped by category
        if profile.skills:
            by_category: Dict[str, List[str]] = {}
            for skill in profile.skills:
                cat = (
                    skill.category
                    if isinstance(skill.category, str)
                    else str(skill.category)
                )
                by_category.setdefault(cat, []).append(skill.name)

            skill_parts = []
            for cat, names in by_category.items():
                skill_parts.append(f"{cat}: {', '.join(names)}")
            skill_text = "Skills:\n" + "\n".join(skill_parts)
            chunks.append(
                TextChunk(
                    content=skill_text,
                    chunk_index=len(chunks),
                    source_id=source_id,
                    source_type="profile",
                    section="skills",
                    token_count=self._estimate_tokens(skill_text),
                )
            )

        # Experience entries
        for exp in profile.experience:
            exp_parts = [f"Experience - {exp.title} at {exp.company}"]
            if exp.description:
                exp_parts.append(exp.description)
            if exp.highlights:
                exp_parts.append("Achievements: " + "; ".join(exp.highlights))
            if exp.technologies:
                exp_parts.append("Technologies: " + ", ".join(exp.technologies))

            exp_text = "\n".join(exp_parts)
            exp_chunks = self.chunk_text(exp_text, source_id, "profile", "experience")
            for c in exp_chunks:
                c.chunk_index = len(chunks)
                chunks.append(c)

        # Projects
        for project in profile.projects:
            proj_parts = [f"Project - {project.name}: {project.description}"]
            if project.technologies:
                proj_parts.append("Technologies: " + ", ".join(project.technologies))
            if project.highlights:
                proj_parts.append("Impact: " + "; ".join(project.highlights))

            proj_text = "\n".join(proj_parts)
            chunks.append(
                TextChunk(
                    content=proj_text,
                    chunk_index=len(chunks),
                    source_id=source_id,
                    source_type="profile",
                    section="project",
                    token_count=self._estimate_tokens(proj_text),
                )
            )

        # Education
        for edu in profile.education:
            edu_text = f"Education - {edu.degree} from {edu.school}"
            chunks.append(
                TextChunk(
                    content=edu_text,
                    chunk_index=len(chunks),
                    source_id=source_id,
                    source_type="profile",
                    section="education",
                    token_count=self._estimate_tokens(edu_text),
                )
            )

        # Target job preferences
        targets = profile.targets
        target_parts = []
        if targets.keywords:
            target_parts.append("Looking for: " + ", ".join(targets.keywords))
        if targets.locations:
            target_parts.append("Preferred locations: " + ", ".join(targets.locations))
        if target_parts:
            target_text = "\n".join(target_parts)
            chunks.append(
                TextChunk(
                    content=target_text,
                    chunk_index=len(chunks),
                    source_id=source_id,
                    source_type="profile",
                    section="targets",
                    token_count=self._estimate_tokens(target_text),
                )
            )

        return chunks

    def _chunk_recursive(self, text: str, max_tokens: int, overlap: int) -> List[str]:
        """Recursively split text by paragraphs, then sentences, then characters.

        Args:
            text: Text to split.
            max_tokens: Maximum tokens per chunk.
            overlap: Token overlap between adjacent chunks.

        Returns:
            List of text pieces.
        """
        paragraphs = text.split("\n\n")
        chunks: List[str] = []
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            candidate = f"{current}\n\n{para}" if current else para

            if self._estimate_tokens(candidate) <= max_tokens:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # If single paragraph exceeds limit, split by sentences
                if self._estimate_tokens(para) > max_tokens:
                    chunks.extend(self._split_by_sentences(para, max_tokens, overlap))
                    current = ""
                else:
                    current = para

        if current:
            chunks.append(current)

        # Apply overlap
        if overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks, overlap)

        return chunks

    def _chunk_fixed(self, text: str, max_tokens: int) -> List[str]:
        """Split text into fixed-size chunks by character count.

        Args:
            text: Text to split.
            max_tokens: Maximum tokens per chunk.

        Returns:
            List of text pieces.
        """
        max_chars = max_tokens * 4  # ~4 chars per token
        pieces = []
        for i in range(0, len(text), max_chars):
            pieces.append(text[i : i + max_chars])
        return pieces

    def _split_by_sentences(
        self, text: str, max_tokens: int, overlap: int
    ) -> List[str]:
        """Split text by sentences when paragraphs are too large.

        Args:
            text: Text to split.
            max_tokens: Maximum tokens per chunk.
            overlap: Token overlap between chunks.

        Returns:
            List of text pieces.
        """
        # Simple sentence splitting on common terminators
        sentences = []
        for part in text.replace("!", ".").replace("?", ".").split("."):
            part = part.strip()
            if part:
                sentences.append(part + "." if not part.endswith(".") else part)

        if not sentences:
            # Fall back to fixed chunking
            return self._chunk_fixed(text, max_tokens)

        chunks: List[str] = []
        current = ""

        for sentence in sentences:
            candidate = f"{current} {sentence}" if current else sentence
            if self._estimate_tokens(candidate) <= max_tokens:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

        if overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks, overlap)

        return chunks

    def _apply_overlap(self, chunks: List[str], overlap_tokens: int) -> List[str]:
        """Add overlap text from the end of each chunk to the beginning of the next.

        Args:
            chunks: List of text chunks.
            overlap_tokens: Number of tokens to overlap.

        Returns:
            List of chunks with overlap applied.
        """
        overlap_chars = overlap_tokens * 4  # ~4 chars per token
        overlapped = []

        for i, chunk in enumerate(chunks):
            if i > 0 and overlap_chars > 0:
                prev_tail = chunks[i - 1][-overlap_chars:]
                chunk = f"{prev_tail} {chunk}"
            overlapped.append(chunk)

        return overlapped

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string.

        Uses a rough heuristic of 4 characters per token.

        Args:
            text: Text to estimate.

        Returns:
            Estimated token count.
        """
        return max(1, len(text) // 4)
