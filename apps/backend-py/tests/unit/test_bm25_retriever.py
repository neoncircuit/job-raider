"""
Unit tests for BM25Retriever.
"""

from src.rag.bm25_retriever import BM25Result, BM25Retriever


class TestBM25IndexAndQuery:
    """Tests for building an index and querying it."""

    def test_query_returns_ranked_results(self):
        """BM25 query returns results sorted by score descending."""
        retriever = BM25Retriever()
        retriever.index_documents(
            doc_ids=["doc_1", "doc_2", "doc_3"],
            documents=[
                "Python engineer with Django and FastAPI experience",
                "Senior Java developer with Spring Boot knowledge",
                "Full-stack Python developer, React and AWS",
            ],
        )

        results = retriever.query("Python developer", n_results=3)

        assert len(results) == 3
        assert results[0].doc_id in ("doc_1", "doc_3")
        assert results[0].score >= results[1].score
        assert results[1].score >= results[2].score

    def test_scores_are_normalized(self):
        """BM25 scores are normalized to 0-1 range."""
        retriever = BM25Retriever()
        retriever.index_documents(
            doc_ids=["doc_1", "doc_2", "doc_3", "doc_4"],
            documents=[
                "Python engineer with Django and FastAPI experience",
                "Senior Java developer with Spring Boot microservices",
                "Full-stack Python developer React and AWS cloud deployment",
                "Data scientist Python machine learning TensorFlow",
            ],
        )

        results = retriever.query("Python developer", n_results=4)

        for r in results:
            assert 0.0 <= r.score <= 1.0
        assert results[0].score == 1.0

    def test_query_returns_result_objects(self):
        """BM25 query returns BM25Result instances with correct fields."""
        retriever = BM25Retriever()
        retriever.index_documents(
            doc_ids=["doc_1"],
            documents=["Machine learning engineer"],
            metadatas=[{"source": "test"}],
        )

        results = retriever.query("machine learning", n_results=1)

        assert len(results) == 1
        assert isinstance(results[0], BM25Result)
        assert results[0].doc_id == "doc_1"
        assert results[0].document == "Machine learning engineer"
        assert results[0].metadata == {"source": "test"}


class TestBM25Tokenization:
    """Tests for the default tokenizer."""

    def test_default_tokenize_extracts_words(self):
        """Default tokenizer extracts lowercase alphanumeric tokens."""
        tokens = BM25Retriever._default_tokenize("Hello, World! 123")
        assert tokens == ["hello", "world", "123"]

    def test_default_tokenize_handles_special_chars(self):
        """Default tokenizer strips punctuation and special characters."""
        tokens = BM25Retriever._default_tokenize("C++ / C# / .NET")
        assert "c" in tokens
        assert "net" in tokens

    def test_default_tokenize_handles_empty_string(self):
        """Default tokenizer returns empty list for empty string."""
        tokens = BM25Retriever._default_tokenize("")
        assert tokens == []


class TestBM25EmptyIndex:
    """Tests for querying an empty or uninitialized index."""

    def test_query_empty_index_returns_empty(self):
        """Querying an empty index returns an empty list."""
        retriever = BM25Retriever()
        results = retriever.query("test query", n_results=5)
        assert results == []

    def test_doc_count_empty(self):
        """doc_count is 0 for a fresh retriever."""
        retriever = BM25Retriever()
        assert retriever.doc_count == 0


class TestBM25AddDocuments:
    """Tests for incrementally adding documents."""

    def test_add_documents_to_existing_index(self):
        """Adding documents extends the existing index."""
        retriever = BM25Retriever()
        retriever.index_documents(
            doc_ids=["doc_1"],
            documents=["Python developer"],
        )

        retriever.add_documents(
            doc_ids=["doc_2"],
            documents=["Java developer"],
        )

        assert retriever.doc_count == 2
        results = retriever.query("Java", n_results=2)
        assert any(r.doc_id == "doc_2" for r in results)

    def test_add_duplicate_doc_id_ignored(self):
        """Adding a document with an existing doc_id is skipped."""
        retriever = BM25Retriever()
        retriever.index_documents(
            doc_ids=["doc_1"],
            documents=["Python developer"],
        )

        retriever.add_documents(
            doc_ids=["doc_1"],
            documents=["Java developer"],
        )

        assert retriever.doc_count == 1


class TestBM25Clear:
    """Tests for clearing the index."""

    def test_clear_empties_index(self):
        """Clear removes all documents from the index."""
        retriever = BM25Retriever()
        retriever.index_documents(
            doc_ids=["doc_1"],
            documents=["Python developer"],
        )

        retriever.clear()

        assert retriever.doc_count == 0
        assert retriever.query("Python") == []

    def test_reindex_after_clear(self):
        """Index can be rebuilt after clearing."""
        retriever = BM25Retriever()
        retriever.index_documents(
            doc_ids=["doc_1"],
            documents=["Python developer"],
        )
        retriever.clear()
        retriever.index_documents(
            doc_ids=["doc_2"],
            documents=["Java developer"],
        )

        assert retriever.doc_count == 1
        results = retriever.query("Java", n_results=1)
        assert len(results) == 1
        assert results[0].doc_id == "doc_2"
