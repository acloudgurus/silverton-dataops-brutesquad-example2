import os
import sys
import pytest
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

# Point Python to the actual implementation module (not this test file)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'pvs_testing')))
import pvs_testing as ms  # Now correctly imports from pvs_testing/pvs_testing.py


def test_no_tables_directory(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    result = ms.fetch_all_sql_files(str(tmp_path))
    assert result == []
    assert any("No tables directory" in msg for msg in caplog.messages)

@patch("pandas.read_sql")
def test_execute_tdv_query_to_dict_failure(mock_read_sql):
    mock_df = MagicMock()
    mock_df.to_dict.side_effect = Exception("to_dict failed")
    mock_read_sql.return_value = mock_df

    td_conn = MagicMock()
    result = ms.execute_tdv_query(td_conn, "SELECT *")
    assert result == {}


def test_folder_list_env_not_set(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.delenv("FOLDER_LIST", raising=False)
    ret = ms.main()
    assert ret is None
    assert any("FOLDER_LIST not found" in msg for msg in caplog.messages)


def test_folder_list_env_invalid_json(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("FOLDER_LIST", "invalid-json")
    with patch.object(ms.logger, "info") as mock_logger:
        ret = ms.main()
        assert mock_logger.call_count > 0


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
    assert "mydb.${dbEnv}.my_proc()" in procs
    assert "mydb.${dbEnv}.another_proc()" in procs


def test_pass_or_fail_pass(caplog):
    result_dict = {"RESPONSE": ["PASSED"]}
    with caplog.at_level(logging.INFO):
        ms.pass_or_fail(result_dict)
        assert "PASSED" in caplog.text


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
    with pytest.raises(Exception, match="DB error"):
        ms.execute_tdv_query(td_conn, "SELECT *")


@patch("pvs_testing.teradatasql.connect")
@patch("pvs_testing.execute_tdv_query")
@patch("pvs_testing.extract_proc_names_from_file", return_value=["mydb.${dbEnv}.sample_proc"])
@patch("pvs_testing.fetch_all_sql_files", return_value=["/fake/path/file.sql"])
@patch("pvs_testing.os.environ.get")
def test_main_path(mock_env_get, mock_fetch, mock_extract, mock_exec_query, mock_connect):
    mock_env_get.side_effect = lambda key: {
        "FOLDER_LIST": '["/fake/path"]',
        "DIRECTORY_LIST": "fake_dir",
        "TDV_USERNAME": "user",
        "TDV_PASSWORD": "pass",
        "ChangeTicket_Num": "1234",
        "CTASK_NUM": "5678"
    }.get(key)

    mock_exec_query.return_value = {"RESPONSE": ["PASSED"]}
    mock_conn = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_conn

    ms.main()
