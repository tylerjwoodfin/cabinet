"""
sanity tests for cabinet
"""

import os
import shutil
import datetime
import json
import pytest
from cabinet import Cabinet

@pytest.fixture(autouse=True, scope="session")
def init():
    """
    Perform a backup in case of data loss arising from tests
    """
    cab = Cabinet()
    folder_to_backup = cab.path_cabinet
    backup_folder = os.path.expanduser("~/cabinet-backups/backup")

    # Create the backup folder if it doesn't exist
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    # Generate the backup file name with timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    backup_filename = f"Cabinet Backup {timestamp}"
    backup_path = os.path.join(backup_folder, backup_filename)

    cab.log(f"Cabinet Test - Creating {backup_path}")

    # Perform the backup by creating a zip file
    shutil.make_archive(backup_path, 'zip', folder_to_backup)

def test_cabinet_initialization_with_default_path_cabinet():
    """
    tests default initialization
    """
    cab = Cabinet()
    # pylint: disable=W0212
    assert cab.path_cabinet == cab._get_config('path_cabinet') or '~/cabinet'


def test_cabinet_initialization_with_custom_path_cabinet():
    """
    tests custom path
    """
    custom_path_cabinet = '/home/test/pytest/path/to/custom/cabinet'
    cab = Cabinet(path_cabinet=custom_path_cabinet)    
    assert cab.path_cabinet == custom_path_cabinet

def test_get_config_non_existing_key():
    """
    Test getting a non-existing key from the config file
    """
    cab = Cabinet()
    key = "non_existing_key"
    expected_value = ""
    # pylint: disable=W0212
    actual_value = cab._get_config(key)
    assert actual_value == expected_value