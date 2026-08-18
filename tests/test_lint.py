"""
Tests for Lint Command in CStation CLI.
"""

import pytest
from cstation.commands.lint.main import _parse_port_binding, run_lint_checks


def test_parse_port_binding():
    assert _parse_port_binding("80") == ("0.0.0.0", 80, "tcp")
    assert _parse_port_binding("8069:8069") == ("0.0.0.0", 8069, "tcp")
    assert _parse_port_binding("127.0.0.1:5432:5432") == ("127.0.0.1", 5432, "tcp")
    assert _parse_port_binding("443:443/udp") == ("0.0.0.0", 443, "udp")


def test_run_lint_checks_passes():
    results = run_lint_checks()
    assert isinstance(results, dict)
    assert "total_checks" in results
    assert "issues" in results
    assert results["total_checks"] > 0
