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
    custom_path_cabinet = '~/pytest/path/to/custom/cabinet'
    cab = Cabinet(path_cabinet=custom_path_cabinet)
    assert cab.path_cabinet == custom_path_cabinet
    assert str(
        cab.path_settings_file) == f"{custom_path_cabinet}/settings.json"
    assert cab.path_log == f"{custom_path_cabinet}/log/"

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

def test_get_existing_attribute():
    """
    Test getting an existing attribute from the JSON file
    """
    settings_json = {
        "person": {
            "tyler": {
                "salary": 50000
            }
        }
    }
    cab = Cabinet()
    cab.settings_json = settings_json

    attribute_path = "person", "tyler", "salary"
    expected_value = 50000
    actual_value = cab.get(*attribute_path)
    assert actual_value == expected_value

def test_get_non_existing_attribute_without_warning():
    """
    Test getting a non-existing attribute without warning
    """
    settings_json = {
        "person": {
            "tyler": {
                "salary": 50000
            }
        }
    }
    cab = Cabinet()
    cab.settings_json = settings_json

    attribute_path = "person", "tyler", "age"
    expected_value = None
    actual_value = cab.get(*attribute_path)
    assert actual_value == expected_value

def test_get_non_existing_attribute_with_warning():
    """
    Test getting a non-existing attribute with warning
    """
    settings_json = {
        "person": {
            "tyler": {
                "salary": 50000
            }
        }
    }
    cab = Cabinet()
    cab.settings_json = settings_json

    attribute_path = "person", "tyler", "age"
    expected_value = None
    actual_value = cab.get(*attribute_path, warn_missing=True)
    assert actual_value == expected_value

def test_get_missing_attribute_in_nested_path():
    """
    Test getting a missing attribute in a nested path
    """
    settings_json = {
        "person": {
            "tyler": {
                "salary": 50000
            }
        }
    }
    cab = Cabinet()
    cab.settings_json = settings_json

    attribute_path = "person", "john", "age"
    expected_value = None
    actual_value = cab.get(*attribute_path, warn_missing=True)
    assert actual_value == expected_value

def test_put_existing_attribute():
    """
    Test putting a value to an existing attribute in the JSON file
    """
    settings_json = {
        "person": {
            "tyler": {
                "salary": 50000
            }
        }
    }
    custom_path_cabinet = '~/pytest/path/to/custom/cabinet'
    cab = Cabinet(path_cabinet=custom_path_cabinet)
    cab.settings_json = settings_json

    attribute_path = "person", "tyler", "salary"
    value = 60000
    cab.put(*attribute_path, value=value)

    assert cab.settings_json["person"]["tyler"]["salary"] == value

def test_put_new_attribute():
    """
    Test putting a value to a new attribute in the JSON file
    """
    settings_json = {
        "person": {
            "tyler": {
                "salary": 50000
            }
        }
    }
    custom_path_cabinet = '~/pytest/path/to/custom/cabinet'
    cab = Cabinet(path_cabinet=custom_path_cabinet)
    cab.settings_json = settings_json

    attribute_path = "person", "tyler", "age"
    value = 30
    cab.put(*attribute_path, value=value)

    assert cab.settings_json["person"]["tyler"]["age"] == value

def test_put_attribute_in_different_file():
    """
    Test putting a value to an attribute in a different JSON file
    """
    custom_path_cabinet = '~/pytest/path/to/custom/cabinet'
    cab = Cabinet(path_cabinet=custom_path_cabinet)

    value = "updated example"
    file_name = "custom.json"

    # Create the custom JSON file with initial data
    custom_file_json = {
        "name": "example",
        "value": 42
    }
    with open(f"{cab.path_cabinet}/{file_name}", "w", encoding="utf8") as file:
        json.dump(custom_file_json, file)

    # Perform the put operation
    cab.put("name", value=value, file_name=file_name)

    # Read the modified JSON file
    with open(f"{cab.path_cabinet}/{file_name}", "r", encoding="utf8") as file:
        modified_json = json.load(file)

    # Assert the attribute value has been updated
    assert modified_json["name"] == value

    # Clean up the custom JSON file
    os.remove(f"{cab.path_cabinet}/{file_name}")
