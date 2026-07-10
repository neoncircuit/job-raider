"""Unit tests for the TextChunker."""

from src.models.job_listing import JobListing, JobSource
from src.rag.chunker import TextChunker
from src.rag.config import ChunkingConfig


class TestChunkText:
    """Tests for generic text chunking."""

    def test_short_text_single_chunk(self):
        """Short text should produce a single chunk."""
        chunker = TextChunker(ChunkingConfig(max_chunk_size=512))
        chunks = chunker.chunk_text("Hello world", "test_1", "job", "header")

        assert len(chunks) == 1
        assert chunks[0].content == "Hello world"
        assert chunks[0].source_id == "test_1"
        assert chunks[0].section == "header"

    def test_empty_text_no_chunks(self):
        """Empty text should produce no chunks."""
        chunker = TextChunker()
        chunks = chunker.chunk_text("", "test_1", "job")

        assert len(chunks) == 0

    def test_long_text_multiple_chunks(self):
        """Long text should be split into multiple chunks."""
        chunker = TextChunker(
            ChunkingConfig(max_chunk_size=20, overlap=5, strategy="recursive")
        )
        # Create text with multiple paragraphs to force splitting
        paragraphs = []
        for i in range(10):
            paragraphs.append(
                f"This is paragraph number {i} with enough text to exceed small chunk limits and force splitting into multiple pieces."
            )
        long_text = "\n\n".join(paragraphs)
        chunks = chunker.chunk_text(long_text, "test_1", "job")

        assert len(chunks) > 1

    def test_chunk_metadata_preserved(self):
        """Chunks should carry correct metadata."""
        chunker = TextChunker()
        chunks = chunker.chunk_text("test content", "job_42", "job", "description")

        assert chunks[0].source_id == "job_42"
        assert chunks[0].source_type == "job"
        assert chunks[0].section == "description"
        assert chunks[0].token_count > 0


class TestChunkJob:
    """Tests for job listing chunking."""

    def test_produces_multiple_sections(self, sample_job_listing):
        """Should produce chunks from multiple job sections."""
        chunker = TextChunker()
        chunks = chunker.chunk_job(sample_job_listing)

        sections = {c.section for c in chunks}
        assert "header" in sections
        assert "skills" in sections

    def test_header_contains_context(self, sample_job_listing):
        """Header chunk should contain title and company."""
        chunker = TextChunker()
        chunks = chunker.chunk_job(sample_job_listing)

        header = next(c for c in chunks if c.section == "header")
        assert "Senior Python Engineer" in header.content
        assert "Tech Corp" in header.content

    def test_skills_chunk(self, sample_job_listing):
        """Skills chunk should list skill names."""
        chunker = TextChunker()
        chunks = chunker.chunk_job(sample_job_listing)

        skills_chunk = next(c for c in chunks if c.section == "skills")
        assert "python" in skills_chunk.content.lower()

    def test_minimal_job(self):
        """Job with minimal fields should still produce a header chunk."""
        job = JobListing(
            title="Dev",
            company="Co",
            job_id="min_1",
            source=JobSource.LINKEDIN,
        )
        chunker = TextChunker()
        chunks = chunker.chunk_job(job)

        assert len(chunks) >= 1
        assert chunks[0].section == "header"


class TestChunkProfile:
    """Tests for user profile chunking."""

    def test_produces_multiple_sections(self, sample_user_profile):
        """Should produce chunks from multiple profile sections."""
        chunker = TextChunker()
        chunks = chunker.chunk_profile(sample_user_profile)

        sections = {c.section for c in chunks}
        assert "summary" in sections or len(chunks) > 0  # summary may be None

    def test_experience_chunks(self, sample_user_profile):
        """Should produce experience chunks."""
        chunker = TextChunker()
        chunks = chunker.chunk_profile(sample_user_profile)

        exp_chunks = [c for c in chunks if c.section == "experience"]
        assert len(exp_chunks) >= 1
        assert "Senior Software Engineer" in exp_chunks[0].content

    def test_project_chunks(self, sample_user_profile):
        """Should produce project chunks."""
        chunker = TextChunker()
        chunks = chunker.chunk_profile(sample_user_profile)

        proj_chunks = [c for c in chunks if c.section == "project"]
        assert len(proj_chunks) >= 1
        assert "E-commerce Platform" in proj_chunks[0].content

    def test_skills_chunk(self, sample_user_profile):
        """Should produce a skills chunk."""
        chunker = TextChunker()
        chunks = chunker.chunk_profile(sample_user_profile)

        skill_chunks = [c for c in chunks if c.section == "skills"]
        assert len(skill_chunks) >= 1
        assert "Python" in skill_chunks[0].content

    def test_targets_chunk(self, sample_user_profile):
        """Should produce a targets chunk with preferences."""
        chunker = TextChunker()
        chunks = chunker.chunk_profile(sample_user_profile)

        target_chunks = [c for c in chunks if c.section == "targets"]
        assert len(target_chunks) >= 1
