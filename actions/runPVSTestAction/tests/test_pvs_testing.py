import os
import pytest
import logging
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pvs_testing as ms
def test_no_tables_directory(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    # tmp_path has no tables subdirectory
    result = ms.fetch_all_sql_files(str(tmp_path))
    assert result == []
    assert any("No tables directory" in msg for msg in caplog.messages)


def test_folder_list_env_not_set(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.delenv("FOLDER_LIST", raising=False)
    ret = ms.main()
    assert ret is None
    assert any("FOLDER_LIST not found" in msg for msg in caplog.messages)


def test_folder_list_env_invalid_json(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("FOLDER_LIST", "invalid-json")
    ret = ms.main()
    assert ret is None
    assert any("Failed to parse FOLDER_LIST" in msg for msg in caplog.messages)


def test_fetch_all_sql_files(tmp_path):
    tables_path = tmp_path / "tables"
    tables_path.mkdir()
    sql_file = tables_path / "test_proc.sql"
    sql_file.write_text("SELECT 1")
    result = ms.fetch_all_sql_files(str(tmp_path))
    assert len(result) == 1
    assert result[0].endswith("test_proc.sql")


def test_extract_proc_names_from_file(tmp_path):
    sql_file = tmp_path / "sample.sql"
    sql_file.write_text("""
        CREATE PROCEDURE mydb.${dbEnv}.my_proc()
        REPLACE PROCEDURE mydb.${dbEnv}.another_proc()
    """)
    procs = ms.extract_proc_names_from_file(str(sql_file))
    assert "mydb.${dbEnv}.my_proc" in procs
    assert "mydb.${dbEnv}.another_proc" in procs


@patch("pvs_testing.execute_tdv_query")
def test_pass_or_fail_pass(mock_exec, capsys):
    result_dict = {"RESPONSE": ["PASSED"]}
    ms.pass_or_fail(result_dict)
    captured = capsys.readouterr()
    assert "PASSED" in captured.out or "PASSED" in captured.err


def test_pass_or_fail_fail_exit():
    result_dict = {"RESPONSE": ["FAILED"]}
    with pytest.raises(SystemExit):
        ms.pass_or_fail(result_dict)


@patch("pandas.read_sql")
def test_execute_tdv_query_success(mock_read_sql):
    mock_df = MagicMock()
    mock_df.to_dict.return_value = {"key": [1]}
    mock_read_sql.return_value = mock_df

    td_conn = MagicMock()
    result = ms.execute_tdv_query(td_conn, "SELECT *")
    assert result == {"key": [1]}


@patch("pandas.read_sql", side_effect=Exception("DB error"))
def test_execute_tdv_query_failure(mock_read_sql):
    td_conn = MagicMock()
    result = ms.execute_tdv_query(td_conn, "SELECT *")
    assert result == {}
