"""Tests for git diff utilities."""

import subprocess

from skpro.utils import git_diff


def test_get_merge_base_ref_prefers_available_refs(monkeypatch):
    """Should pick the first available git reference from the candidate list."""
    git_diff.get_merge_base_ref.cache_clear()
    seen = []

    def mock_check_output(cmd, text=True, stderr=None):
        seen.append(cmd)
        ref = cmd[-1]
        if ref == "main":
            return ref
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    assert git_diff.get_merge_base_ref() == "main"
    assert seen == [
        ["git", "rev-parse", "--verify", "remotes/origin/main"],
        ["git", "rev-parse", "--verify", "remotes/origin/master"],
        ["git", "rev-parse", "--verify", "main"],
    ]


def test_get_changed_lines_returns_empty_without_merge_base(monkeypatch):
    """Missing merge base should not shell out to git diff or raise errors."""
    git_diff.get_merge_base_ref.cache_clear()
    monkeypatch.setattr(git_diff, "get_merge_base_ref", lambda: None)

    def fail_check_output(*args, **kwargs):
        raise AssertionError("git diff should not be called without a merge base")

    monkeypatch.setattr(subprocess, "check_output", fail_check_output)

    assert git_diff.get_changed_lines("pyproject.toml") == []


def test_is_module_changed_defaults_to_true_without_merge_base(monkeypatch):
    """Missing merge base should conservatively mark modules as changed."""
    git_diff.is_module_changed.cache_clear()
    monkeypatch.setattr(git_diff, "get_merge_base_ref", lambda: None)
    monkeypatch.setattr(git_diff, "get_path_from_module", lambda module_str: module_str)

    assert git_diff.is_module_changed("skpro.utils.git_diff") is True
