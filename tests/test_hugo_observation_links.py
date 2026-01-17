"""Tests for Hugo observation link post-processing."""

from pathlib import Path

from src.hugo.generator import HugoGenerator


class TestHugoObservationLinks:
    """Test that references to observations are linked correctly."""

    def test_link_observation_references_basic(self, tmp_path, monkeypatch):
        # Set up a fake content directory with one existing observation post
        content_dir = tmp_path / "content" / "posts"
        content_dir.mkdir(parents=True, exist_ok=True)
        post_file = content_dir / "2025-12-30_162640_observation_45.md"
        post_file.write_text("dummy", encoding="utf-8")

        gen = HugoGenerator()

        # Monkeypatch the generator's content_dir to use our temp directory
        monkeypatch.setattr(gen, "content_dir", content_dir)

        diary = "This builds on what I noticed back in Observation #45 near the river."

        processed = gen._link_observation_references(diary)

        assert "[Observation #45](/posts/2025-12-30_162640_observation_45)" in processed

    def test_link_observation_references_no_match(self, tmp_path, monkeypatch):
        # No posts exist for the referenced observation ID
        content_dir = tmp_path / "content" / "posts"
        content_dir.mkdir(parents=True, exist_ok=True)

        gen = HugoGenerator()
        monkeypatch.setattr(gen, "content_dir", content_dir)

        diary = "This builds on what I noticed back in Observation #999."

        processed = gen._link_observation_references(diary)

        # Text should be unchanged when no matching slug is found
        assert processed == diary

    def test_link_observation_references_narrow_nbsp(self, tmp_path, monkeypatch):
        # Test that narrow no-break space (\u202F) is handled correctly
        # This is what the LLM sometimes outputs
        content_dir = tmp_path / "content" / "posts"
        content_dir.mkdir(parents=True, exist_ok=True)
        post_file = content_dir / "2025-12-30_162640_observation_45.md"
        post_file.write_text("dummy", encoding="utf-8")

        gen = HugoGenerator()
        monkeypatch.setattr(gen, "content_dir", content_dir)

        # Use narrow no-break space (\u202F) instead of regular space
        diary = "- **Observation\u202f#45 (21\u202fDec\u202f2025)** recorded"

        processed = gen._link_observation_references(diary)

        assert "[Observation\u202f#45](/posts/2025-12-30_162640_observation_45)" in processed

    def test_link_standalone_hash_pattern(self, tmp_path, monkeypatch):
        # Test that standalone "#NN" (without "Observation") is also linked
        content_dir = tmp_path / "content" / "posts"
        content_dir.mkdir(parents=True, exist_ok=True)
        post_file = content_dir / "2025-12-30_162640_observation_45.md"
        post_file.write_text("dummy", encoding="utf-8")

        gen = HugoGenerator()
        monkeypatch.setattr(gen, "content_dir", content_dir)

        diary = "This reminds me of #45 from last week."

        processed = gen._link_observation_references(diary)

        assert "[#45](/posts/2025-12-30_162640_observation_45)" in processed

    def test_link_both_patterns(self, tmp_path, monkeypatch):
        # Test that both "Observation #NN" and "#NN" are linked in the same text
        content_dir = tmp_path / "content" / "posts"
        content_dir.mkdir(parents=True, exist_ok=True)
        post_file1 = content_dir / "2025-12-30_162640_observation_45.md"
        post_file1.write_text("dummy", encoding="utf-8")
        post_file2 = content_dir / "2025-12-31_162640_observation_46.md"
        post_file2.write_text("dummy", encoding="utf-8")

        gen = HugoGenerator()
        monkeypatch.setattr(gen, "content_dir", content_dir)

        diary = "In #45 I saw this, and Observation #46 confirmed it."

        processed = gen._link_observation_references(diary)

        assert "[#45](/posts/2025-12-30_162640_observation_45)" in processed
        assert "[Observation #46](/posts/2025-12-31_162640_observation_46)" in processed
        assert processed.count("/posts/") == 2

    def test_fix_malformed_header_links(self, tmp_path, monkeypatch):
        # Test that malformed headers like "##[# 1]" are fixed to "## 1" (no link in headers)
        content_dir = tmp_path / "content" / "posts"
        content_dir.mkdir(parents=True, exist_ok=True)
        post_file = content_dir / "2025-12-12_observation_1.md"
        post_file.write_text("dummy", encoding="utf-8")

        gen = HugoGenerator()
        monkeypatch.setattr(gen, "content_dir", content_dir)

        # Test malformed header with space
        diary = "##[# 1](/posts/2025-12-12_observation_1). Snapshot\nSome text here."
        processed = gen._link_observation_references(diary)
        assert "## 1" in processed
        assert "##[# 1]" not in processed
        assert "## [1](/posts/" not in processed  # Headers should not have links

        # Test malformed header without space
        diary2 = "##[#1](/posts/2025-12-12_observation_1). Snapshot\nSome text here."
        processed2 = gen._link_observation_references(diary2)
        assert "## 1" in processed2
        assert "##[#1]" not in processed2
        assert "## [1](/posts/" not in processed2  # Headers should not have links

        # Test with multiple hash marks
        diary3 = "###[# 2](/posts/2025-12-12_observation_1). Section\nSome text."
        processed3 = gen._link_observation_references(diary3)
        assert "### 2" in processed3
        assert "###[# 2]" not in processed3
        assert "### [2](/posts/" not in processed3  # Headers should not have links

        # Test already-linked header should be cleaned
        diary4 = "## [1](/posts/2025-12-12_observation_1). Snapshot\nSome text here."
        processed4 = gen._link_observation_references(diary4)
        assert "## 1" in processed4
        assert "## [1](/posts/" not in processed4  # Link should be removed from header