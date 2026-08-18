"""
Tests for Output Formatting in CStation CLI.
"""

import json
import yaml
import pytest
from cstation.output import OutputFormat, print_formatted


def test_output_format_enum():
    assert OutputFormat.JSON == "json"
    assert OutputFormat.YAML == "yaml"
    assert OutputFormat.TABLE == "table"


def test_print_formatted_json(capsys):
    data = [{"name": "test_vps", "status": "running"}]
    print_formatted(data, format_type=OutputFormat.JSON)
    captured = capsys.readouterr().out
    parsed = json.loads(captured)
    assert parsed == data


def test_print_formatted_yaml(capsys):
    data = [{"name": "test_vps", "status": "running"}]
    print_formatted(data, format_type=OutputFormat.YAML)
    captured = capsys.readouterr().out
    parsed = yaml.safe_load(captured)
    assert parsed == data


def test_print_formatted_table_callback(capsys):
    called = []
    def callback():
        called.append(True)
        print("TABLE_RENDERED")

    print_formatted({"any": "data"}, format_type=OutputFormat.TABLE, table_renderer=callback)
    assert called == [True]
    assert "TABLE_RENDERED" in capsys.readouterr().out
