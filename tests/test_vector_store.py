"""Tests for vector-store backend selection.

No network and no Chroma client is constructed here: what matters is that the
choice of backend is unambiguous, that a misconfigured cloud setup fails with
a message naming what is missing, and that it never quietly falls back to
writing embeddings somewhere the user did not ask for.
"""

import pytest

from policy_rag import config, vector_store


@pytest.fixture
def cloud(monkeypatch):
    """Configures a fully credentialed cloud backend."""
    monkeypatch.setattr(config, "VECTOR_BACKEND", "cloud")
    monkeypatch.setattr(config, "CHROMA_API_KEY", "ck-test")
    monkeypatch.setattr(config, "CHROMA_TENANT", "tenant-1")
    monkeypatch.setattr(config, "CHROMA_DATABASE", "policies")


def test_local_is_the_default(monkeypatch):
    """Cloning the repo and running ingest must not require an account."""
    monkeypatch.setattr(config, "VECTOR_BACKEND", "local")
    assert vector_store.backend() == vector_store.BACKEND_LOCAL


def test_backend_name_is_case_and_space_insensitive(monkeypatch):
    """A value typed into .env should not fail on stray whitespace or caps."""
    monkeypatch.setattr(config, "VECTOR_BACKEND", "  Cloud ")
    assert vector_store.backend() == vector_store.BACKEND_CLOUD


def test_unknown_backend_is_rejected(monkeypatch):
    """A typo must fail loudly rather than silently defaulting."""
    monkeypatch.setattr(config, "VECTOR_BACKEND", "pinecone")
    with pytest.raises(ValueError, match="not a known backend"):
        vector_store.backend()


def test_cloud_without_credentials_names_what_is_missing(monkeypatch):
    """The error has to be actionable: which variables are not set."""
    monkeypatch.setattr(config, "VECTOR_BACKEND", "cloud")
    monkeypatch.setattr(config, "CHROMA_API_KEY", "")
    monkeypatch.setattr(config, "CHROMA_TENANT", "")
    monkeypatch.setattr(config, "CHROMA_DATABASE", "")

    assert vector_store.missing_cloud_credentials() == [
        "CHROMA_API_KEY", "CHROMA_TENANT", "CHROMA_DATABASE",
    ]
    with pytest.raises(RuntimeError) as excinfo:
        vector_store.get_client()
    message = str(excinfo.value)
    assert "CHROMA_API_KEY" in message
    assert "RAG_VECTOR_BACKEND=local" in message  # tells the user the way out


def test_partial_credentials_still_fail(monkeypatch, cloud):
    """Two out of three is not a working configuration."""
    monkeypatch.setattr(config, "CHROMA_TENANT", "")
    assert vector_store.missing_cloud_credentials() == ["CHROMA_TENANT"]
    with pytest.raises(RuntimeError, match="CHROMA_TENANT"):
        vector_store.get_client()


def test_describe_identifies_the_backend(monkeypatch, cloud):
    """Health output and ingest logs must make the destination obvious."""
    assert vector_store.describe() == "Chroma Cloud (tenant-1/policies)"
    monkeypatch.setattr(config, "VECTOR_BACKEND", "local")
    assert "local" in vector_store.describe()
    assert str(config.CHROMA_DIR) in vector_store.describe()


def test_readiness_requires_the_local_docstore_in_cloud_mode(monkeypatch, cloud, tmp_path):
    """Cloud embeddings alone are not enough - auto-merging needs the docstore."""
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path / "absent")
    assert vector_store.is_ready() is False

    present = tmp_path / "storage"
    present.mkdir()
    monkeypatch.setattr(config, "STORAGE_DIR", present)
    assert vector_store.is_ready() is True


def test_readiness_requires_both_stores_locally(monkeypatch, tmp_path):
    """Locally, the embeddings directory must exist too."""
    monkeypatch.setattr(config, "VECTOR_BACKEND", "local")
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setattr(config, "STORAGE_DIR", storage)
    monkeypatch.setattr(config, "CHROMA_DIR", tmp_path / "absent")
    assert vector_store.is_ready() is False

    chroma = tmp_path / "chroma"
    chroma.mkdir()
    monkeypatch.setattr(config, "CHROMA_DIR", chroma)
    assert vector_store.is_ready() is True


def test_local_reset_removes_only_the_embeddings(monkeypatch, tmp_path):
    """Reset clears the vector store; the caller handles the docstore."""
    monkeypatch.setattr(config, "VECTOR_BACKEND", "local")
    chroma = tmp_path / "chroma"
    chroma.mkdir()
    (chroma / "chroma.sqlite3").write_text("data", encoding="utf-8")
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setattr(config, "CHROMA_DIR", chroma)
    monkeypatch.setattr(config, "STORAGE_DIR", storage)

    vector_store.reset()
    assert not chroma.exists()
    assert storage.exists()


def test_local_reset_is_safe_when_nothing_exists(monkeypatch, tmp_path):
    """A first run must not fail because there is nothing to delete."""
    monkeypatch.setattr(config, "VECTOR_BACKEND", "local")
    monkeypatch.setattr(config, "CHROMA_DIR", tmp_path / "never-created")
    vector_store.reset()
