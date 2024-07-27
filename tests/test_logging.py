# pylint: disable=missing-function-docstring
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=line-too-long
# pylint: disable=redefined-outer-name

import io
import os
import sys
import json
import logging
from datetime import date
from unittest.mock import patch, MagicMock
import pytest
from cabinet import Cabinet

@pytest.fixture(scope='function')
def mock_config():
    # Define the mock configuration data
    mock_data = {
        "mongodb_username": "fake_user",
        "mongodb_password": "fake_pass",
        "mongodb_cluster_name": "fake_cluster",
        "mongodb_db_name": "fake_db",
        "path_cabinet": "fake_path",
        "editor": "nvim"
    }

    # Define the path where the mock config should be created
    config_path = os.path.expanduser('~/.config/cabinet/config.json')

    # Ensure the directory exists
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    # Write the mock configuration to the file
    with open(config_path, 'w', encoding="utf-8") as f:
        json.dump(mock_data, f, indent=4)

    # Yield to the test
    yield

    # Cleanup after test (optional, if you want to remove the file after the test)
    if os.path.exists(config_path):
        os.remove(config_path)

@pytest.fixture
def cabinet(mock_config):
    # Create a Cabinet instance with the mock configuration
    return Cabinet()

def test_log_default_parameters(cabinet):
    """
    Test that the default logging parameters use the 'info' level and the default logger name.
    """
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        cabinet.log('Test message')

        mock_logger.info.assert_called_once_with('Test message')

def test_log_custom_level(cabinet):
    """
    Test that a custom log level (e.g., 'error') is correctly used when logging a message.
    """
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        cabinet.log('Test message', level='error')

        mock_logger.error.assert_called_once_with('Test message')

def test_log_invalid_level(cabinet):
    """
    Test that an invalid log level raises a ValueError.
    """
    with pytest.raises(ValueError):
        cabinet.log('Test message', level='invalid_level')

def test_log_warn_level(cabinet):
    """
    Test that the 'warn' level is converted to 'warning' and used correctly.
    """
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        cabinet.log('Test message', level='warn')

        mock_logger.warning.assert_called_once_with('Test message')

def test_log_file_creation(cabinet, tmp_path):
    """
    Test that a log file is created in the specified log folder path.
    """
    log_folder = tmp_path / 'logs'

    # Call the log function with the temporary path
    cabinet.log('Test message', log_folder_path=str(log_folder))

    # Check if the log folder was actually created
    assert log_folder.exists(), f"Log folder was not created at {log_folder}"

    # Check if the log file was actually created
    today = str(date.today())
    expected_log_file = log_folder / f"LOG_DAILY_{today}.log"
    assert expected_log_file.exists(), f"Log file was not created at {expected_log_file}"

    # Optionally, check the content of the log file
    with open(expected_log_file, 'r', encoding="utf-8") as f:
        log_content = f.read()
        assert 'Test message' in log_content, "Test message was not written to the log file"

def test_log_quiet_mode(cabinet):
    """
    Test that when 'is_quiet' is True, no output is printed to stdout and no stream handler is added.
    """
    captured_output = io.StringIO()
    sys.stdout = captured_output

    try:
        with patch('os.makedirs'), \
             patch('logging.FileHandler') as mock_file_handler, \
             patch('logging.getLogger') as mock_get_logger:

            # Setup mock logger
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            # Setup mock file handler
            mock_file_handler.return_value = MagicMock()
            mock_file_handler.return_value.level = logging.NOTSET

            cabinet.log('Test quiet message', is_quiet=True)

        output = captured_output.getvalue()

        # Check that nothing was printed to stdout
        assert output.strip() == ''

        # Check that the log message was passed to the logger
        mock_logger.info.assert_called_once_with('Test quiet message')

        # Check that no stream handler was added
        assert all(not isinstance(call.args[0], logging.StreamHandler)
                   for call in mock_logger.addHandler.call_args_list)

    finally:
        sys.stdout = sys.__stdout__

def test_log_custom_log_name(cabinet):
    """
    Test that a custom logger name is used if provided.
    """
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        cabinet.log('Test message', log_name='custom_log')

        mock_get_logger.assert_called_once_with('custom_log')

def test_log_default_log_name(cabinet):
    """
    Test that the default log name uses the 'LOG_DAILY_' prefix and the current date.
    """
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        today = str(date.today())
        expected_log_name = f"LOG_DAILY_{today}"

        cabinet.log('Test message')

        mock_get_logger.assert_called_once_with(expected_log_name)

@pytest.mark.parametrize("level", ['debug', 'info', 'warning', 'error', 'critical'])
def test_log_all_valid_levels(level, cabinet):
    """
    Test that all valid log levels ('debug', 'info', 'warning', 'error', 'critical') are correctly used.
    """
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        cabinet.log('Test message', level=level)

        getattr(mock_logger, level).assert_called_once_with('Test message')

def test_log_file_path_creation(cabinet, tmp_path):
    """
    Test that the FileHandler is created with the correct file path based on the provided log folder path.
    """
    log_folder = tmp_path / 'logs'
    mock_file_handler_instance = MagicMock()
    mock_file_handler_instance.level = logging.NOTSET

    with patch('os.makedirs'), patch('logging.FileHandler', return_value=mock_file_handler_instance) as mock_file_handler:
        cabinet.log('Test message', log_folder_path=str(log_folder))

        today = str(date.today())
        expected_log_file = log_folder / f"LOG_DAILY_{today}.log"

        mock_file_handler.assert_called_once_with(str(expected_log_file), mode='a')
