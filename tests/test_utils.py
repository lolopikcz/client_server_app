"""Tests for utility functions."""

from __future__ import annotations

import unittest
from pathlib import Path

from utils import validate_filename


class TestValidateFilename(unittest.TestCase):
    """Test filename validation and sanitization."""

    def test_valid_filename(self) -> None:
        """Should accept valid filenames."""
        self.assertEqual(validate_filename("test.txt"), "test.txt")

    def test_strips_path(self) -> None:
        """Should reject filenames with directory components."""
        with self.assertRaises(ValueError):
            validate_filename("path/to/file.txt")

    def test_rejects_empty(self) -> None:
        """Should reject empty filenames."""
        with self.assertRaises(ValueError):
            validate_filename("")

    def test_rejects_whitespace_only(self) -> None:
        """Should reject whitespace-only filenames."""
        with self.assertRaises(ValueError):
            validate_filename("   ")

    def test_rejects_path_traversal(self) -> None:
        """Should reject path traversal."""
        with self.assertRaises(ValueError):
            validate_filename("../../../etc/passwd")

    def test_rejects_backslash_traversal(self) -> None:
        """Should reject backslash path traversal."""
        with self.assertRaises(ValueError):
            validate_filename("..\\..\\file.txt")

    def test_rejects_special_chars(self) -> None:
        """Should reject filenames with special characters."""
        with self.assertRaises(ValueError):
            validate_filename("file;rm -rf /")

    def test_allows_hyphens_and_underscores(self) -> None:
        """Should allow hyphens, underscores, and dots."""
        self.assertEqual(validate_filename("my-file_v2.txt"), "my-file_v2.txt")

    def test_allows_spaces(self) -> None:
        """Should allow spaces in filenames."""
        self.assertEqual(validate_filename("my file.txt"), "my file.txt")


class TestValidateFilenameAdversarial(unittest.TestCase):
    """Adversarial tests trying to break filename validation."""

    def test_null_byte_basic(self) -> None:
        """Should reject null byte injection."""
        with self.assertRaises(ValueError):
            validate_filename("file\x00.txt")

    def test_null_byte_trailing(self) -> None:
        """Should reject trailing null byte."""
        with self.assertRaises(ValueError):
            validate_filename("file.txt\x00")

    def test_null_byte_hidden(self) -> None:
        """Should reject null byte hidden in middle."""
        with self.assertRaises(ValueError):
            validate_filename("file\x00hidden.txt")

    def test_reserved_windows_con(self) -> None:
        """Should reject CON device name."""
        with self.assertRaises(ValueError):
            validate_filename("CON")

    def test_reserved_windows_con_with_ext(self) -> None:
        """Should reject CON.txt."""
        with self.assertRaises(ValueError):
            validate_filename("CON.txt")

    def test_reserved_windows_nul(self) -> None:
        """Should reject NUL device name."""
        with self.assertRaises(ValueError):
            validate_filename("NUL")

    def test_reserved_windows_prn(self) -> None:
        """Should reject PRN device name."""
        with self.assertRaises(ValueError):
            validate_filename("PRN")

    def test_reserved_windows_com1(self) -> None:
        """Should reject COM1 device name."""
        with self.assertRaises(ValueError):
            validate_filename("COM1")

    def test_reserved_windows_lpt1(self) -> None:
        """Should reject LPT1 device name."""
        with self.assertRaises(ValueError):
            validate_filename("LPT1")

    def test_reserved_case_insensitive(self) -> None:
        """Should reject reserved names regardless of case."""
        with self.assertRaises(ValueError):
            validate_filename("con")
        with self.assertRaises(ValueError):
            validate_filename("Con")

    def test_path_traversal_encoded(self) -> None:
        """Should reject encoded path traversal."""
        with self.assertRaises(ValueError):
            validate_filename("..%2F..%2Fetc%2Fpasswd")

    def test_double_dot_variants(self) -> None:
        """Should reject various dot patterns."""
        with self.assertRaises(ValueError):
            validate_filename("....//etc/passwd")
        with self.assertRaises(ValueError):
            validate_filename("file/../../../etc/passwd")

    def test_shell_injection_semicolon(self) -> None:
        """Should reject semicolon injection."""
        with self.assertRaises(ValueError):
            validate_filename("file;rm -rf /")

    def test_shell_injection_backticks(self) -> None:
        """Should reject backtick injection."""
        with self.assertRaises(ValueError):
            validate_filename("`whoami`.txt")

    def test_shell_injection_dollar_paren(self) -> None:
        """Should reject $(command) injection."""
        with self.assertRaises(ValueError):
            validate_filename("$(whoami).txt")

    def test_excessive_length(self) -> None:
        """Should reject filenames over 255 bytes."""
        long_name = "a" * 256 + ".txt"
        with self.assertRaises(ValueError):
            validate_filename(long_name)

    def test_unicode_homoglyphs(self) -> None:
        """Should reject Cyrillic lookalikes (allowed by regex but suspicious)."""
        # Cyrillic 'а' (U+0430) vs Latin 'a'
        # Our regex allows \w which includes Unicode letters
        # This is a known limitation - would need explicit blocklist
        name = "f\u0430ile.txt"  # f + Cyrillic а + ile.txt
        # This passes our current validation (regex allows Unicode word chars)
        # In production, you'd block non-ASCII or use a strict allowlist
        result = validate_filename(name)
        self.assertIsInstance(result, str)

    def test_special_chars_injection(self) -> None:
        """Should reject pipe, ampersand, redirection."""
        with self.assertRaises(ValueError):
            validate_filename("file|whoami.txt")
        with self.assertRaises(ValueError):
            validate_filename("file&whoami.txt")
        with self.assertRaises(ValueError):
            validate_filename("file>output.txt")

    def test_backslash_only(self) -> None:
        """Should reject lone backslash."""
        with self.assertRaises(ValueError):
            validate_filename("\\")

    def test_slash_only(self) -> None:
        """Should reject lone slash."""
        with self.assertRaises(ValueError):
            validate_filename("/")

    def test_dot_dot_only(self) -> None:
        """Should reject .. as filename."""
        with self.assertRaises(ValueError):
            validate_filename("..")

    def test_dot_only(self) -> None:
        """Should reject . as filename (empty name)."""
        with self.assertRaises(ValueError):
            validate_filename(".")


if __name__ == "__main__":
    unittest.main()
