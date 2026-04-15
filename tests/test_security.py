"""Security tests for coding agent tools."""

import pytest
import tempfile
from pathlib import Path
import os

from coding_agent.tools import validate_path, read_file, list_files, edit_file, MAX_FILE_SIZE


class TestPathTraversal:
    """Test path traversal protection."""

    def test_validates_normal_path(self, tmp_path):
        """Normal paths should work."""
        os.chdir(tmp_path)
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = validate_path("test.txt")
        assert result == test_file

    def test_blocks_parent_directory(self, tmp_path):
        """Should block .. traversal."""
        os.chdir(tmp_path)

        with pytest.raises(ValueError, match="Path traversal"):
            validate_path("../etc/passwd")

    def test_blocks_double_dot_variations(self, tmp_path):
        """Should block actual path traversal attempts."""
        os.chdir(tmp_path)

        # These actually do traverse to parent directory
        actual_traversals = [
            ".//../etc/passwd",
            "foo/../../etc/passwd",
            "../../../etc/passwd",
        ]

        for variation in actual_traversals:
            with pytest.raises(ValueError, match="Path traversal"):
                validate_path(variation)

    def test_handles_weird_but_safe_paths(self, tmp_path):
        """Paths like ....// are weird but safe (they're subdirectories)."""
        os.chdir(tmp_path)

        # These look suspicious but actually resolve to subdirs in cwd
        # ....//foo resolves to ./..../foo (subdir named "....")
        weird_safe_paths = [
            "....//etc/passwd",  # Resolves to ./..../etc/passwd
            "..././etc/passwd",  # Resolves to ./.../etc/passwd
        ]

        # Should not raise - these are safe
        for path in weird_safe_paths:
            result = validate_path(path)
            # Should resolve to something under tmp_path
            assert tmp_path in result.parents or result == tmp_path

    def test_blocks_absolute_paths_outside_cwd(self, tmp_path):
        """Should block absolute paths outside working directory."""
        os.chdir(tmp_path)

        with pytest.raises(ValueError, match="Path traversal"):
            validate_path("/etc/passwd")

    def test_allows_subdirectories(self, tmp_path):
        """Should allow subdirectories."""
        os.chdir(tmp_path)
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = validate_path("subdir")
        assert result == subdir

    def test_rejects_empty_path(self, tmp_path):
        """Should reject empty paths."""
        os.chdir(tmp_path)

        with pytest.raises(ValueError, match="empty"):
            validate_path("")


class TestFileSizeLimits:
    """Test file size protection."""

    def test_reads_normal_file(self, tmp_path):
        """Should read normal-sized files."""
        os.chdir(tmp_path)
        test_file = tmp_path / "test.txt"
        content = "Hello, World!"
        test_file.write_text(content)

        result = read_file("test.txt")
        assert result == content

    def test_blocks_large_file_read(self, tmp_path):
        """Should block reading files larger than MAX_FILE_SIZE."""
        os.chdir(tmp_path)
        test_file = tmp_path / "large.txt"

        # Create a file larger than MAX_FILE_SIZE
        with open(test_file, 'wb') as f:
            f.write(b'x' * (MAX_FILE_SIZE + 1))

        result = read_file("large.txt")
        assert "too large" in result.lower()

    def test_blocks_large_content_write(self, tmp_path):
        """Should block writing content larger than MAX_FILE_SIZE."""
        os.chdir(tmp_path)

        large_content = "x" * (MAX_FILE_SIZE + 1)
        result = edit_file("test.txt", "", large_content)
        assert "too large" in result.lower()


class TestBinaryFileProtection:
    """Test binary file handling."""

    def test_detects_binary_file(self, tmp_path):
        """Should detect and reject binary files."""
        os.chdir(tmp_path)
        test_file = tmp_path / "binary.bin"
        test_file.write_bytes(b'\x00\x01\x02\x03\xff\xfe')

        result = read_file("binary.bin")
        # Error message includes unicode decode error info
        assert "error" in result.lower()
        assert ("utf-8" in result.lower() or "decode" in result.lower())


class TestListFilesSecurity:
    """Test list_files security."""

    def test_blocks_parent_directory_listing(self, tmp_path):
        """Should block listing parent directories."""
        os.chdir(tmp_path)

        result = list_files("..")
        assert "Path traversal" in result or "Error" in result

    def test_validates_directory_exists(self, tmp_path):
        """Should validate directory exists."""
        os.chdir(tmp_path)

        result = list_files("nonexistent")
        assert "Error" in result


class TestEditFileSecurity:
    """Test edit_file security."""

    def test_blocks_path_traversal_edit(self, tmp_path):
        """Should block editing files outside working directory."""
        os.chdir(tmp_path)

        result = edit_file("../../../etc/passwd", "", "hacked")
        assert "Path traversal" in result or "Error" in result

    def test_creates_file_safely(self, tmp_path):
        """Should create files only in working directory."""
        os.chdir(tmp_path)

        result = edit_file("newfile.txt", "", "content")
        assert "Created" in result
        assert (tmp_path / "newfile.txt").exists()
        assert (tmp_path / "newfile.txt").read_text() == "content"

    def test_validates_target_is_text_file(self, tmp_path):
        """Should detect binary files on edit."""
        os.chdir(tmp_path)
        test_file = tmp_path / "binary.bin"
        test_file.write_bytes(b'\x00\x01\x02\x03')

        result = edit_file("binary.bin", "old", "new")
        # When reading existing binary file for edit, will get decode error
        # Either "not a text file" or "old_content not found" (if it somehow reads)
        assert "error" in result.lower()


class TestInputValidation:
    """Test input validation."""

    def test_rejects_none_path(self, tmp_path):
        """Should reject None as path."""
        os.chdir(tmp_path)

        with pytest.raises((ValueError, TypeError)):
            validate_path(None)

    def test_handles_missing_file(self, tmp_path):
        """Should handle missing files gracefully."""
        os.chdir(tmp_path)

        result = read_file("nonexistent.txt")
        assert "not found" in result.lower()
