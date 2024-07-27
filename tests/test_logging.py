# pylint: disable=missing-function-docstring
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=line-too-long
# pylint: disable=redefined-outer-name

import sys
import io
import logging
from datetime import date
from unittest.mock import patch, MagicMock
import pytest
from cabinet import Cabinet

@pytest.fixture
def cabinet():
    return Cabinet()

def test_log_default_parameters(cabinet):
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        cabinet.log('Test message')

        mock_logger.info.assert_called_once_with('Test message')

def test_log_custom_level(cabinet):
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        cabinet.log('Test message', level='error')

        mock_logger.error.assert_called_once_with('Test message')

def test_log_invalid_level(cabinet):
    with pytest.raises(ValueError):
        cabinet.log('Test message', level='invalid_level')

def test_log_warn_level(cabinet):
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        cabinet.log('Test message', level='warn')

        mock_logger.warning.assert_called_once_with('Test message')

def test_log_file_creation(cabinet, tmp_path):
    log_folder = tmp_path / 'logs'
    with patch('os.makedirs') as mock_makedirs:
        cabinet.log('Test message', log_folder_path=str(log_folder))
        mock_makedirs.assert_called_once_with(log_folder)

def test_log_quiet_mode(cabinet):
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

def test_log_not_quiet_mode(cabinet):
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

            cabinet.log('Test non-quiet message', is_quiet=False)

        output = captured_output.getvalue()

        # Check that the message was printed to stdout
        assert 'Test non-quiet message' in output

        # Check that the log message was passed to the logger
        mock_logger.info.assert_called_once_with('Test non-quiet message')

        # Check that a stream handler was added
        assert any(isinstance(call.args[0], logging.StreamHandler)
                   for call in mock_logger.addHandler.call_args_list)

    finally:
        sys.stdout = sys.__stdout__

def test_log_custom_log_name(cabinet):
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        cabinet.log('Test message', log_name='custom_log')

        mock_get_logger.assert_called_once_with('custom_log')

def test_log_default_log_name(cabinet):
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        today = str(date.today())
        expected_log_name = f"LOG_DAILY_{today}"

        cabinet.log('Test message')

        mock_get_logger.assert_called_once_with(expected_log_name)

@pytest.mark.parametrize("level", ['debug', 'info', 'warning', 'error', 'critical'])
def test_log_all_valid_levels(level, cabinet):
    with patch('os.makedirs'), patch('logging.FileHandler'), patch('logging.getLogger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        cabinet.log('Test message', level=level)

        getattr(mock_logger, level).assert_called_once_with('Test message')

def test_log_file_path_creation(cabinet, tmp_path):
    log_folder = tmp_path / 'logs'
    with patch('os.makedirs'), patch('logging.FileHandler') as mock_file_handler:
        cabinet.log('Test message', log_folder_path=str(log_folder))

        today = str(date.today())
        expected_log_file = log_folder / f"LOG_DAILY_{today}.log"

        mock_file_handler.assert_called_once_with(str(expected_log_file), mode='a')
