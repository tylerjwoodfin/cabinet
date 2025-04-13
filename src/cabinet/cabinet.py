# pylint: disable=too-many-lines

"""
Cabinet provides a simple interface for storing and retrieving data in a centralized location.

It includes a variety of utility methods for managing files, logging, and managing configurations.

Usage:
    ```
    from cabinet import Cabinet

    cab = Cabinet()
    ```
"""
import inspect
import os
import ast
import sys
import json
import logging
import pathlib
import argparse
import subprocess
import importlib.metadata
from html import escape
from datetime import date, datetime, timedelta, timezone
from typing import Any, Type, Optional, TypeVar, Union
import pymongo.errors
from prompt_toolkit import print_formatted_text, HTML
from pymongo.errors import PyMongoError, OperationFailure, ConnectionFailure
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.database import Database
from bson import json_util, ObjectId
from . import helpers
from .constants import (
    NEW_SETUP_MSG_INTRO,
    NEW_SETUP_MSG_CHECK_MONGODB,
    NEW_SETUP_MSG_MONGODB_INSTRUCTIONS,
    CONFIG_MONGODB_DB_NAME,
    CONFIG_MONGODB_CONNECTION_STRING,
    CONFIG_PATH_DIR_LOG,
    CONFIG_EDITOR,
    EDIT_FILE_DEFAULT,
    ERROR_CONFIG_MISSING_VALUES,
    ERROR_CONFIG_JSON_DECODE,
    ERROR_CONFIG_FILE_INVALID_MONGODB,
    ERROR_CONFIG_INVALID_EDITOR,
    ERROR_CONFIG_BROKEN_EDITOR,
    ERROR_LOCAL_STORAGE_JSON_DECODE,
    ERROR_MONGODB_TIMEOUT,
    ERROR_MONGODB_DNS,
    WARN_LOCAL_STORAGE_PATH,
)
from .mail import Mail
from importlib.metadata import version


class Cabinet:
    """
    Cabinet class
    """

    mongodb_enabled: bool = False
    mongodb_db_name: str = ''
    mongodb_cluster_name: str = '' # derived from mongodb_connection_string
    mongodb_connection_string: str = ''
    mongodb_uri = ""
    client: MongoClient | None = None
    database: Database
    path_dir_config = helpers.resolve_path("~/.config/cabinet")
    path_dir_cabinet: str = helpers.resolve_path("~/.cabinet")
    path_dir_log: str = f"{path_dir_cabinet}/log"
    path_file_config: str = f"{path_dir_config}/config.json"
    path_file_cache: str = f"{path_dir_config}/cache.json"
    path_file_data: str = f"{path_dir_cabinet}/data.json"
    editor: str = 'nano'
    cached_data: dict = {}
    is_new_setup: bool = False

    def _get_config(self, key=None, warn_missing=True):
        """
        Retrieves the value associated with the specified key from the configuration file.
        The configuration file is located at ~/.config/cabinet/config.json.

        Args:
            key (str): The key to retrieve the corresponding value.
                - If None, the entire configuration dictionary is returned.
                - Default is None.

        Returns:
            The value associated with the specified key in the configuration file. If the key is not
            found, an empty string is returned.

        Raises:
            FileNotFoundError: If the configuration file is not found.
            KeyError: If the key is not found in the configuration file.
            JSONDecodeError: If there is a problem decoding the JSON data in the configuration file.

        Notes:
            If the JSON data in the configuration file is not valid,
            the user will be given the option
            to overwrite the file with an empty dictionary or fix the file manually.
        """

        def get_editor():
            # List of common terminal text editors
            editors = ["nano", "vim", "nvim", "emacs", "vi", "pico", "mcedit"]

            # Check if each editor is available in the system's PATH
            available_editors = []
            for editor in editors:
                result = subprocess.run(["which", editor],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        check=False)
                if result.returncode == 0:
                    available_editors.append(editor)

            # Display the available editors to the user for selection
            if available_editors:
                print("Available editors:")
                for i, editor in enumerate(available_editors, start=1):
                    print(f"{i}. {editor}")

                selection = input(CONFIG_EDITOR)
                try:
                    selected_editor = available_editors[int(selection) - 1]
                    return selected_editor
                except (IndexError, ValueError):
                    print(ERROR_CONFIG_INVALID_EDITOR)
                    return "nano"
            else:
                print("No common terminal text editors found. Defaulting to 'nano'.")
                return "nano"

        def config_prompts(key=None):
            value = ""
            if key == 'mongodb_db_name':
                value = input(CONFIG_MONGODB_DB_NAME)
            if key == 'mongodb_connection_string':
                value = input(CONFIG_MONGODB_CONNECTION_STRING)
            if key == 'path_dir_log':
                value = input(CONFIG_PATH_DIR_LOG) or "~/.cabinet/log"
            if key == 'editor':
                value = get_editor()

            if value:
                self._put_config(key, value)

            return value

        try:
            with open(self.path_file_config, 'r+', encoding="utf8") as file:
                return json.load(file)[key]
        except FileNotFoundError:
            # setup
            self.is_new_setup = True

            # Create the .cabinet directory if it doesn't exist
            path_cabinet = helpers.resolve_path("~/.cabinet")
            if not pathlib.Path(path_cabinet).exists():
                os.makedirs(path_cabinet)

            while True:
                storage_type = input(NEW_SETUP_MSG_INTRO).strip()
                if storage_type in {'1', '2'}:
                    break
                print("Please enter 1 or 2.")

            if storage_type == "1":
                if input(NEW_SETUP_MSG_CHECK_MONGODB).lower().startswith("y"):
                    self._put_config("mongodb_enabled", True)
                else:
                    print(NEW_SETUP_MSG_MONGODB_INSTRUCTIONS)
            elif storage_type == "2":
                self._put_config("mongodb_enabled", False)

            return config_prompts(key)
        except KeyError:
            if self.is_new_setup:
                return config_prompts(key)
            elif warn_missing:
                print(
                    f"Warning: Could not find {key} in {self.path_file_config}")
            return ""
        except json.decoder.JSONDecodeError:
            err_msg = f"Problem reading {self.path_file_config}.\n\n{ERROR_CONFIG_JSON_DECODE}"
            response = input(err_msg)

            if response.lower().startswith("y"):
                with open(self.path_file_config, 'w+', encoding="utf8") as file:
                    file.write('{}')
                print("Done. Please try again.")
            else:
                print(f"OK. Please fix {self.path_file_config} and try again.")

            sys.exit(-1)

    def _put_config(self, key: str | None = None, value: Any | None = None) -> Any | None:
        """
        Updates the configuration file at ~/.config/cabinet/config.json with
        the specified key-value pair.

        Args:
            key (str): The key for the configuration setting.
            value (Any): The value for the configuration setting (JSON-compatible).

        Returns:
            Any: The updated value for the configuration setting.

        Raises:
            FileNotFoundError: If the configuration file cannot be found.
        """

        if value is None:
            print("No changes were made.")
            sys.exit(1)

        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.path_file_config), exist_ok=True)

            # Open the file for reading and writing, or create it if it doesn't exist
            with open(self.path_file_config, 'r+', encoding="utf8") as file:
                config = json.load(file)
        except FileNotFoundError:
            # Create the file and write an empty JSON object
            with open(self.path_file_config, 'x+', encoding="utf8") as file:
                self._ifprint(
                    "Note: Could not find an existing config file; creating a new one.",
                    self.is_new_setup is False
                )
                file.write('{}')
                config = {}

        # Update the configuration with the provided key-value pair
        if key is not None:
            config[key] = value

            # Write the updated config back to the file
            with open(self.path_file_config, 'w', encoding="utf8") as file:
                json.dump(config, file, indent=4)

        return config.get(key)

    def _ifprint(self, message: str, is_print: bool):
        """
        Prints the message if `print` is true.
        """

        # check for valid JSON
        try:
            json.loads(message)
            if is_print:
                print(json.dumps(message, indent=2))
        except TypeError:
            if is_print:
                print(json.dumps(message, indent=2))
        except json.JSONDecodeError:
            if is_print:
                print(message)
            return message

    def _run_editor(self, editor: str, file_path: str) -> None:
        """
        Runs the specified editor on the provided file path,
        using `--wait` if the editor is VS Code.
        """
        if editor.lower() in ["code", "vscode"]:
            # Use the --wait flag for VS Code to ensure it blocks until the file is closed
            print("Opening in VS Code. Data will be updated after the file is closed.")
            subprocess.run([editor, "--wait", file_path], check=True)
        else:
            # Run the specified editor normally
            subprocess.run([editor, file_path], check=True)

    def __init__(self):
        """
        Initializes the Cabinet instance with the provided or default configuration.

        Notes:
            - The configuration is read from ~/.config/cabinet/config.json.
            - Data is stored in ~/.cabinet/data.json (local) or MongoDB (remote).
            - The attributes of the Cabinet instance are set based on the configuration values.

        Raises:
            pymongo.errors.InvalidURI: If the MongoDB URI is invalid.
            pymongo.errors.ServerSelectionTimeoutError:
                If there is a timeout while connecting to the MongoDB server.
            pymongo.errors.ConfigurationError: If there is an error in the MongoDB configuration.

        Returns:
            None

        """

        keys = ["mongodb_enabled", "editor", "path_dir_log"]

        # for compatibility, set mongodb_enabled to True if all MongoDB keys are present
        if all(self._get_config(key, warn_missing=False) for key in keys[1:]):
            if self._get_config("mongodb_enabled", warn_missing=False) == '':
                self._put_config("mongodb_enabled", True)
                self.mongodb_enabled = True

        # If MongoDB is enabled, include MongoDB-specific keys in the check
        if self._get_config("mongodb_enabled", warn_missing=False) or False:
            keys.extend(["mongodb_db_name", "mongodb_connection_string"])

        for key in keys:
            value = self._get_config(key, warn_missing=False)

            # path_dir_log is optional and defaults to ~/.cabinet/log if unset
            if key == "path_dir_log" and value == "":
                continue

            # warn if mongodb_connection_string contains '<db_password>'
            if key == "mongodb_connection_string" and "<db_password>" in value:
                self.log(
                    "Please replace '<db_password>' in mongodb_connection_string "
                    "with your actual password.",
                    level="warn"
                )

            setattr(self, key, value)

        # derive cluster from mongodb_connection_string
        if self.mongodb_connection_string:
            try:
                self.mongodb_cluster_name = self.mongodb_connection_string.split(
                    '@')[1].split('.')[0]
            except IndexError:
                self.log("Could not get cluster from mongodb_connection_string", level="warn")
                self.mongodb_cluster_name = "unknown"

        # check for missing relevant keys
        keys.remove("path_dir_log")
        if any(getattr(self, key) is None or getattr(self, key) == '' for key in keys):
            input(ERROR_CONFIG_MISSING_VALUES)
            self.config()
            sys.exit(-1)

        self.is_new_setup = False

        # Check if MongoDB is enabled
        if self.mongodb_enabled:
            try:
                self.client = MongoClient(self.mongodb_connection_string, server_api=ServerApi('1'))
                self.database = self.client[self.mongodb_db_name]

                if self.database is None:
                    self.log("Database cannot be initialized", level="error")
                    return None
            except pymongo.errors.InvalidURI as error:
                print(ERROR_CONFIG_FILE_INVALID_MONGODB)
                print(error._message)
                sys.exit(-1)
            except pymongo.errors.ServerSelectionTimeoutError as error:
                print(ERROR_MONGODB_TIMEOUT)
                print(error)
                sys.exit(-1)
            except pymongo.errors.ConfigurationError as error:
                print(ERROR_MONGODB_DNS)
                print(error)
                sys.exit(-1)
        else:
            # Resolve local storage path (~/.cabinet/data.json)

            # Load cached data from local JSON file
            if os.path.exists(self.path_file_data):
                try:
                    with open(self.path_file_data, 'r', encoding='utf-8') as data_file:
                        self.cached_data = json.load(data_file)
                except json.decoder.JSONDecodeError:
                    err_msg = f"Problem reading {self.path_file_data}.\n\n"
                    err_msg += f"{ERROR_LOCAL_STORAGE_JSON_DECODE}"
                    response = input(err_msg)

                    if response.lower().startswith("y"):
                        with open(self.path_file_data, 'w+', encoding="utf8") as file:
                            file.write('{}')
                        print("Done. Please try again.")
                    else:
                        print(f"OK. Please fix {self.path_file_data} and try again.")

                    sys.exit(-1)
            else:
                self.log(WARN_LOCAL_STORAGE_PATH, level="warn")
                # require user to press enter to continue
                input()
                try:
                    # Attempt to create the missing file
                    with open(self.path_file_data, 'w+', encoding="utf8") as file:
                        file.write('{}')
                    self.log("New data file created successfully.", level="info", is_quiet=True)
                except IOError as e:
                    # Handle potential file creation errors
                    self.log(f"Failed to create data file: {str(e)}", level="error")
                    raise

        # verify path_dir_log exists
        if not os.path.exists(self.path_dir_log):
            os.makedirs(self.path_dir_log)

    def config(self):
        """
        Opens the configuration file for editing using the default editor.

        If the function is called from a terminal, the configuration file is opened with the default
        editor defined in the 'EDITOR' environment variable.
        If the 'EDITOR' variable is not set, 'vi'
        is used as the default editor.

        If the function is called from a non-terminal environment,
        such as a graphical user interface,
        the behavior depends on the operating system:
        - On Windows, the configuration file is opened using
        the default associated editor for JSON files.
        - On macOS, the configuration file is opened using
        the default application associated with JSON files.
        - On Linux, the configuration file is opened using
        the default application for opening files with
        the 'xdg-open' command.

        If none of the above conditions are met, a message is displayed
        instructing the user to manually
        edit the configuration file.

        Raises:
            FileNotFoundError:
                If the default editor or the associated application for opening files is not found.

        Notes:
            - The configuration file is defined by the 'path_config_file' attribute of the class.
            - The function uses the 'subprocess.run' method
            to execute the necessary command for opening the file.
            - The 'check=True' argument ensures that an error
            is raised if the command execution fails.

        """

        if os.isatty(sys.stdin.fileno()):
            # User is in a terminal, open with default editor
            try:
                subprocess.run(
                    [os.environ.get('EDITOR', 'vi'), self.path_file_config], check=True)
            except FileNotFoundError:
                print("Default editor not found. Unable to open the file.")
        else:
            if sys.platform.startswith('win32'):
                # Windows
                subprocess.run(
                    ['start', '', self.path_file_config], shell=True, check=True)
            elif sys.platform.startswith('darwin'):
                # macOS
                subprocess.run(['open', self.path_file_config], check=True)
            elif sys.platform.startswith('linux'):
                # Linux
                subprocess.run(['xdg-open', self.path_file_config], check=True)
            else:
                print(f"Please edit ${self.path_file_config} to configure.")

    def update_cache(self, path: str | None = None, force: bool = False) -> str | None:
        """
        Writes all MongoDB data to a cache file for faster reads in most situations.
        Creates the cache file if it does not exist.

        Args:
            - path (str): full path, including filename, of cache.json
            - force (bool): update cache regardless of how  old cache file is.
                - overridden to 'true' if caller function is `put`.
        """

        if not self.mongodb_enabled:
            return None

        force_update: bool =  force or inspect.stack()[1].function == 'put'

        if path is None:
            path = self.path_file_cache

        # Check if cache file exists and is less than 1 hour old
        if not force_update and os.path.exists(path):
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(path))
            if datetime.now() - file_mod_time < timedelta(hours=1):
                with open(path, "r", encoding="utf-8") as cache_file:
                    self.cached_data = json.load(cache_file)
                return None

        collection_data = self.database.cabinet.find()
        json_data = json.dumps(list(collection_data), indent=4, default=json_util.default)

        try:
            # Ensure the directory exists and write the JSON data to cache
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as temp_file:
                temp_file.write(json_data)
        except OSError as e:
            self.log(f"Error updating cache: {e}", level="error")
            return None

        self.cached_data = json.loads(json_data)

        return json_data

    def edit_cabinet(self, editor: str | None = None) -> None:
        """
        Opens the data in self.database.cabinet within a JSON file in
        Nano (default) or the editor specified in `cabinet --config` -> `editor`.
        When the file is closed, it replaces the data in this collection in MongoDB.

        Args:
            - editor (str, optional): The editor to use, potentially overriding
                the default. Specified from the terminal with `--editor`.
        """

        if editor is None:
            editor = self.editor

        # Handle local storage
        if not self.mongodb_enabled:
            # Open path_data_json if it exists; otherwise, display a warning
            if not os.path.exists(self.path_file_data):
                self.log(WARN_LOCAL_STORAGE_PATH, level="warn")
                return
            self._run_editor(editor, self.path_file_data)
            return

        json_data = self.update_cache(self.path_file_cache, force=True)

        try:
            # Edit the cache file
            self._run_editor(editor, self.path_file_cache)

            # Read the modified JSON data from the cache
            with open(self.path_file_cache, "r", encoding="utf-8") as file_cache:
                modified_json_data = file_cache.read()

            # Check if any changes were made
            if modified_json_data == json_data:
                print("No changes.")
                return

            # Replace the data in the collection with the modified data
            modified_data = json.loads(modified_json_data)
            for document in modified_data:
                document.pop("_id", None)  # Remove the existing _id field
                document["_id"] = ObjectId()  # Assign a new ObjectId

            self.database.cabinet.drop()  # Drop the existing collection
            self.database.cabinet.insert_many(modified_data)  # Insert the modified data

            print("Data in the collection has been updated.")

            self.update_cache(force=True)

        except FileNotFoundError as err:
            if editor and f"'{editor}'" in str(err):
                self.log(ERROR_CONFIG_BROKEN_EDITOR.replace("%", editor), level="error")
                self._put_config("editor", "nano")
            else:
                print(f"Error: Cache file not found in {self.path_file_cache} after cache update.")
        except subprocess.CalledProcessError:
            print(f"Error: Failed to open the file in '{editor}'.")
        except json.JSONDecodeError:
            self.log("Failed to parse the modified JSON data.", level="error")
            self.log("Refreshing cache with original data.", level="info")
            self.write_file('cache.json', self.path_dir_config, json_data)
        except Exception as error:  # pylint: disable=W0703
            print(f"Error: {str(error)}")

    def edit_file(self, file_path: str | None = None,
                create_if_not_exist: bool = True,
                editor: str | None = None) -> None:
        """
        Edit and save a file in Nano (default) or specified editor in `cabinet --config`.

        Args:
            - file_path (str, optional): The path to the file to edit.
                Allows for shortcuts by setting paths in MongoDB -> path -> edit

            - create_if_not_exist (bool, optional): Whether to create the file if it does not exist.
                Defaults to False.

            - editor (str, optional): The editor to use, potentially overriding
                the default. Specified from the terminal with `--editor`.

        Raises:
            - ValueError: If the file_path is not a string.

            - FileNotFoundError: If the file does not exist and create_if_not_exist is False.

        Returns:
            None
        """

        if editor is None:
            editor = self.editor

        path_edit = self.get("path", "edit")

        # Edit Cabinet's MongoDB directly if no file_path
        if file_path is None:
            path = input(EDIT_FILE_DEFAULT)

            if path == "":
                self.edit_cabinet(editor)
                return

            self.edit_file(path)
            return

        # Allows for shortcuts by setting paths in MongoDB -> path -> edit
        if path_edit and file_path in path_edit:
            item = self.get("path", "edit", file_path)
            if not isinstance(item, dict) or "value" not in item.keys():
                self.log(f"Could not use shortcut for {file_path} in getItem(path -> edit); "
                        f"should be a JSON object with value", level="warn")
            else:
                file_path = item["value"]

        if not file_path:
            print("Error: No file_path")
            return

        if not os.path.exists(file_path):
            if create_if_not_exist:
                with open(file_path, "w", encoding="utf-8"):
                    pass
            else:
                self.log("Could not find file to edit", level="error")
                raise FileNotFoundError(f"File does not exist: {file_path}")

        # Cache original file to check for differences
        with open(file_path, "r", encoding="utf-8") as file:
            original_contents = file.readlines()

        # Use _run_editor to open the file in the specified editor
        self._run_editor(editor, file_path)

        # Check for changes after editing
        with open(file_path, "r", encoding="utf-8") as file:
            new_contents = file.readlines()

        if original_contents == new_contents:
            print("No changes.")

    def merge_nested_data(self, existing_data, new_data):
        """
        Merge Nested Data
        """
        merged_data = {}

        for key, value in existing_data.items():
            if key in new_data and isinstance(value, dict) and isinstance(new_data[key], dict):
                merged_data[key] = self.merge_nested_data(value, new_data[key])
            else:
                merged_data[key] = value

        for key, value in new_data.items():
            if key not in merged_data:
                merged_data[key] = value
            else:
                if isinstance(value, dict) and isinstance(merged_data[key], dict):
                    merged_data[key] = self.merge_nested_data(
                        merged_data[key], value)
                else:
                    merged_data[key] = value

        return merged_data

    def put(self, *attribute, value=None, is_print: bool = False):
        """
        Adds or replaces a property
        """

        def parse_arg(value):
            """
            Infer the value type (e.g., 2.0 will not be parsed as an int but as a float)
            """
            if value == "null":
                return None
            try:
                if '.' in str(value) or 'e' in str(value).lower():
                    return float(value)
                return int(value)
            except ValueError:
                if isinstance(value, str):
                    if value.lower() == 'true':
                        return True
                    if value.lower() == 'false':
                        return False
                    try:
                        return ast.literal_eval(value)
                    except (SyntaxError, ValueError):
                        return value
                return value
            except TypeError:
                return value

        custom_filter = {}

        if value is None:  # Check if value argument is None
            value = parse_arg(attribute[-1])

        cache = value
        json_structure = {}
        for item in reversed(attribute[:-1]):
            try:
                json_structure = {}
                json_structure[item] = cache
                cache = json_structure
            except TypeError as error:
                print(error)

        if self.mongodb_enabled:
            existing_data = self.database.cabinet.find_one({}, {"_id": 0})
        else:
            # read from ~/.cabinet/data.json
            with open(self.path_file_data, "r", encoding="utf-8") as file:
                existing_data = json.load(file)

        if existing_data is None:
            self.log("Could not fetch MongoDB data after update", level="error")
            return None

        # Merge the new data with the existing data
        if self.mongodb_enabled:
            update = {"$set": {}}

            if len(attribute) > 2:
                update["$set"][attribute[0]] = self.merge_nested_data(existing_data.get(
                    attribute[0], {}), json_structure[attribute[0]])
            else:
                update = {"$set": json_structure}

            result = self.database.cabinet.update_many(custom_filter, update)
        else:
            # write to ~/.cabinet/data.json
            with open(self.path_file_data, "w", encoding="utf-8") as file:
                json.dump(self.merge_nested_data(existing_data, json_structure), file, indent=4)

        if is_print:
            if self.mongodb_enabled:
                print(f"Modified {result.modified_count} item(s)")
                print(
                    f"{' -> '.join(attribute[:-1])} set to {value}\n")
            else:
                print(f"{' -> '.join(attribute[:-1])} set to {value}\n")

        self.update_cache()

        return value

    T = TypeVar('T', bound=Any)  # Generic type variable for return_type
    def get(self, *attributes, warn_missing: bool = False, is_print: bool = False,
        force_cache_update: bool = False,
        return_type: Optional[Type[T]] = None) -> Union[T, Any, None]:

        """
        Returns JSON-formatted data from local storage (~/.cabinet/data.json) or MongoDB,
        using a cache file to improve performance (if MongoDB enabled).

        Args:
            *attributes (str): A sequence of strings representing nested attributes.
            warn_missing (bool, optional): Whether to warn if an attribute is missing.
            is_print (bool, optional): Whether to print the return value.
            force_cache_update (bool, optional): For MongoDB. Whether to force a fresh MongoDB call.
            return_type (Type[T], optional): The expected return type of the result.
                Defaults to object, which includes any type.

        Returns:
            The value of the attribute if it exists in the cache or MongoDB,
            cast to return_type, otherwise None.

        Usage:
            get('person', 'tyler', 'salary')  # Returns the value of person -> tyler -> salary
        """

        # handle local storage
        if not self.mongodb_enabled:
            # read from ~/.cabinet/data.json
            with open(self.path_file_data, "r", encoding="utf-8") as file:
                data = json.load(file)
                result = data
                for attribute in attributes:
                    if isinstance(result, dict) and attribute in result:
                        result = result[attribute]
                    else:
                        if warn_missing:
                            self.log(f"Attribute '{attribute}' is missing", level="warn")
                        return None

                if is_print:
                    if isinstance(result, dict):
                        print(json.dumps(result, indent=4))
                    else:
                        print(result)

                # Handle return_type if specified
                if return_type is not None:
                    try:
                        return return_type(result)
                    except (ValueError, TypeError) as e:
                        self.log(f"Error casting result to {return_type}: {str(e)}", level="error")
                        return None
                else:
                    # If no specific return_type is needed, return as Any
                    return result

        # handle MongoDB
        cache_update_needed = force_cache_update

        # Check if cache data is available and not expired
        if not force_cache_update and hasattr(self, 'cached_data') \
            and 'expiresAt' in self.cached_data:

            expires_at = datetime.fromisoformat(self.cached_data['expiresAt'])
            cache_update_needed = datetime.now(timezone.utc) >= expires_at

        if cache_update_needed or not self.cached_data:
            self.update_cache()

        # Process the cached data
        for document in self.cached_data:
            result = document
            for attribute in attributes:
                if isinstance(result, dict) and attribute in result:
                    result = result[attribute]
                else:
                    if warn_missing:
                        self.log(f"Attribute '{attribute}' is missing", level="warn")
                    return None

            if isinstance(result, str):
                result = helpers.resolve_path(result)

            if is_print:
                if isinstance(result, dict):
                    print(json.dumps(result, indent=4))
                else:
                    print(result)

            # Handle return_type if specified
            if return_type is not None:
                try:
                    return return_type(result)
                except (ValueError, TypeError) as e:
                    self.log(f"Error casting result to {return_type}: {str(e)}", level="error")
                    return None
            else:
                # return as-is if no specific return_type is needed
                return result  # type: ignore

        if warn_missing:
            storage_type: str = "cache or MongoDB" if self.mongodb_enabled else "local storage"
            self.log(f"'{attributes}' not found in {storage_type}", level="warn")
        return None

    def remove(self, *attribute: str, is_print: bool = False):
        """
        Removes a property from the data in the MongoDB collection.

        Args:
            attribute: A variable length argument list representing \
                the nested structure of the attribute to remove.
            is_print (bool): Whether to print the result of the removal operation.

        Example:
            To remove the nested attribute `a.b.c`, call remove('a', 'b', 'c').
        """

        if not attribute or len(attribute) < 1:
            raise ValueError("At least one attribute must be provided")

        custom_filter = {}

        cache = attribute[-1]
        json_structure = {}
        for item in reversed(attribute[:-1]):
            try:
                json_structure = {}
                json_structure[item] = cache
                cache = json_structure
            except TypeError as error:
                print(error)

        if len(attribute) > 1:
            update = {"$unset": {attribute[0]: json_structure[attribute[0]]}}
        else:
            json_structure[attribute[0]] = 1
            update = {"$unset": json_structure}

        try:
            result = self.database.cabinet.update_many(custom_filter, update)
        except ConnectionFailure as e:
            print(f"Connection failure: {e}")
            return
        except OperationFailure as e:
            print(f"Operation failure: {e}")
            return
        except PyMongoError as e:
            print(f"General PyMongo error: {e}")
            return
        # pylint: disable=W0703
        except Exception as e:
            print(f"Unexpected error: {e}")
            return

        if is_print:
            print(f"Modified {result.modified_count} item(s)")
            print(f"{' -> '.join(attribute)} removed\n")

    def log(self, message: str = '', log_name: str | None = None, level: str | None = None,
        log_folder_path: str | None = None, is_quiet: bool = False) -> None:
        """
        Logs a message using the specified log level
        and writes it to a file if a file path is provided.

        Args:
            message (str, optional): The message to log. Defaults to ''.
            log_name (str, optional): The name of the logger to use. Defaults to None.
            level (str, optional): The log level to use.
                Must be one of 'debug', 'info', 'warning', 'error', or 'critical'.
                Defaults to 'info'.
            log_folder_path (str, optional): The path to the log file.
                If not provided, logs will be saved to MongoDB -> path -> log.
                Defaults to None.
            is_quiet (bool, optional): If True, logging output will be silenced. Defaults to False.

        Raises:
            ValueError: If an invalid log level is provided.

        Returns:
            None
        """

        if not message:
            raise ValueError("Message cannot be empty")

        if level is None:
            level = 'info'

        if level == 'warn':
            level = 'warning'

        valid_levels = {'debug', 'info', 'warning', 'error', 'critical'}
        if level.lower() not in valid_levels:
            raise ValueError(f"Invalid log level: {level}. Must be in {', '.join(valid_levels)}.")

        # Set up color mapping for console output
        color_map = {
            'debug': 'ansiwhite',
            'info': 'ansigreen',
            'warning': 'ansiyellow',
            'error': 'ansired',
            'critical': 'ansimagenta'
        }

        # Custom console handler to only print colored level and message
        class ColorConsoleHandler(logging.StreamHandler):
            """
            Allows for colorful console logs
            """
            def emit(self, record):
                color = color_map[record.levelname.lower()]
                msg = self.format(record)
                escaped_msg = escape(msg)

                print_formatted_text(HTML(f'<{color}>'
                                        f'{record.levelname}: {escaped_msg}</{color}>'))

        # Configure logger
        today = str(date.today())
        log_folder_path = log_folder_path or \
            os.path.join(self.path_dir_log, today)
        log_folder_path = os.path.expanduser(log_folder_path)

        if not os.path.exists(log_folder_path):
            os.makedirs(log_folder_path)

        if log_name is None:
            log_name = f"LOG_DAILY_{today}"

        # Get or create logger
        logger = logging.getLogger(log_name)
        logger.setLevel(getattr(logging, level.upper()))

        # Clear existing handlers if they exist
        if logger.hasHandlers():
            logger.handlers = []

        # File handler for writing complete logs
        file_handler = logging.FileHandler(os.path.join(
            log_folder_path, f"{log_name}.log"), mode='a')

        # Determine the caller's filename and line number
        stack = inspect.stack()
        for frame_info in stack:
            module = inspect.getmodule(frame_info.frame)
            module_name = module.__name__ if module else None
            if module_name and module_name != __name__ and 'logging' not in module_name:
                caller_file = os.path.join(os.path.basename(os.path.dirname(frame_info.filename)),
                           os.path.basename(frame_info.filename))
                caller_line = frame_info.lineno
                break

        file_handler.setFormatter(logging.Formatter(
            f"%(asctime)s — %(levelname)s -> {caller_file}:{caller_line} -> %(message)s"))
        logger.addHandler(file_handler)

        # Add color console handler if not is_quiet
        if not is_quiet:
            console_handler = ColorConsoleHandler()
            console_handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(console_handler)

        # Log the message
        getattr(logger, level.lower())(message)

    def logdb(self, message: str = '', db_name: str | None = None, cluster_name: str | None = None,
            collection_name: str = 'logs', level: str | None = None) -> None:
        """
        Logs a message to MongoDB using the specified database and cluster names.
        Falls back to configured values if not provided.

        Args:
            message (str, optional): The message to log. Defaults to ''.
            db_name (str, optional): The name of the MongoDB database to use.
                If not provided, uses the configured database name.
            cluster_name (str, optional): The name of the MongoDB cluster to use.
                If not provided, use cluster from `mongodb_connection_string`.
            collection_name (str, optional): The name of the collection to store logs in.
                Defaults to 'logs'.
            level (str, optional): The log level to use.
                Must be one of 'debug', 'info', 'warning', 'error', or 'critical'.
                Defaults to 'info'.

        Raises:
            ValueError: If an invalid log level is provided or MongoDB is not enabled.
            pymongo.errors.PyMongoError: If there is an error connecting to MongoDB.

        Returns:
            None
        """
        if not self.mongodb_enabled:
            raise ValueError("MongoDB must be enabled to use logdb")

        if not message:
            raise ValueError("Message cannot be empty")

        if level is None:
            level = 'info'

        if level == 'warn':
            level = 'warning'

        valid_levels = {'debug', 'info', 'warning', 'error', 'critical'}
        if level.lower() not in valid_levels:
            raise ValueError(f"Invalid log level: {level}. Must be in {', '.join(valid_levels)}.")

        # Use provided values or fall back to configured ones
        db_name = db_name or self.mongodb_db_name
        cluster_name = cluster_name or self.mongodb_cluster_name

        try:
            # Determine the caller's filename and line number
            stack = inspect.stack()
            caller_file = "unknown"
            caller_line = 0
            for frame_info in stack:
                module = inspect.getmodule(frame_info.frame)
                module_name = module.__name__ if module else None
                if module_name and module_name != __name__ and 'logging' not in module_name:
                    caller_file = os.path.join(
                        os.path.basename(os.path.dirname(frame_info.filename)),
                                            os.path.basename(frame_info.filename))
                    caller_line = frame_info.lineno
                    break

            # Create log entry
            log_entry = {
                "timestamp": datetime.now(timezone.utc),
                "level": level.upper(),
                "message": message,
                "source": {
                    "file": caller_file,
                    "line": caller_line
                }
            }

            # Insert the log entry
            self.database[collection_name].insert_one(log_entry)

            # Print to console with color (matching the log method's behavior)
            color_map = {
                'debug': 'ansiwhite',
                'info': 'ansigreen',
                'warning': 'ansiyellow',
                'error': 'ansired',
                'critical': 'ansimagenta'
            }
            color = color_map[level.lower()]
            escaped_msg = escape(message)
            print_formatted_text(HTML(f'<{color}>{level.upper()}: {escaped_msg}</{color}>'))

        except pymongo.errors.InvalidURI as error:
            print(f"Invalid MongoDB URI: {error}")
            raise
        except pymongo.errors.ServerSelectionTimeoutError as error:
            print(f"MongoDB connection timeout: {error}")
            raise
        except pymongo.errors.ConfigurationError as error:
            print(f"MongoDB configuration error: {error}")
            raise
        except Exception as error:
            print(f"Unexpected error while logging to MongoDB: {error}")
            raise

    def get_file_as_array(self, file_name: str, file_path: str = '', strip: bool = True,
                          ignore_not_found: bool = False):
        """
        Reads a file and returns its contents as a list of lines.
        The file is assumed to be encoded in UTF-8.

        Args:
            - file_name (str): The filename to read.
            - file_path (str, optional): The path to the directory containing the file.
                If None, ~/.cabinet is used.
            - strip (bool, optional): Whether to strip the lines of whitespace characters
                On by default.
            - ignore_not_found (bool, optional): Whether to return None when the file is not found.
                False by default.

        Returns:
            A list of lines, or None if the file is not found and ignore_not_found is True.
        """

        if not file_path:
            file_path = self.path_dir_cabinet
        elif file_path == "notes":
            file_path = self.get('path', 'notes') or "~/.cabinet/notes"

        if not file_path[-1] == '/':
            file_path += '/'

        try:
            content = open(file_path + file_name, "r", encoding="utf8").read()

            if strip:
                content = content.strip()

            return content.split('\n')
        except FileNotFoundError as error:
            if not ignore_not_found:
                self.log(f"get_file_as_array: {error}", level="error")
            return None

    def write_file(self, file_name: str, path_file: str = '',
                content: Optional[str] = None, append: bool = False,
                is_quiet: bool = False) -> bool:
        """
        Writes a file to the specified path, creating necessary subfolders.
        Resolves aliases in paths.

        Args:
            file_name (str): the name of the file to write.
            path_file (str, optional): the directory path for the file.
                Uses default log path if empty.
                Use 'notes' for cabinet -> path -> notes
            content (str, optional): the content to write to the file.
                Creates an empty file if none.
            append (bool, optional): set to true to append to the file instead of overwriting.
                Defaults to false.
            is_quiet (bool, optional): set to true to suppress status messages.
                Defaults to false.

        Returns:
            True if the file was successfully written, False otherwise.
        """
        try:
            # Handle default file path and notes alias
            if not path_file:
                path_file = helpers.resolve_path(self.path_dir_log)
            elif path_file == "notes":
                path_notes: str = self.get('path', 'notes', return_type=str) or ''
                path_file = helpers.resolve_path(
                    path_notes or self.path_dir_log or '~/.cabinet/notes')

            # Create directory if it does not exist
            os.makedirs(path_file, exist_ok=True)

            # Full path to the file
            full_path = os.path.join(path_file, file_name)

            # Check if appending and the file exists and is not empty
            if append and os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                with open(full_path, 'r+', encoding="utf8") as file:
                    file.seek(0, os.SEEK_END)  # Move to the end of file
                    file.seek(file.tell() - 1, os.SEEK_SET)  # Move back one character
                    if file.read(1) != '\n':
                        content = '\n' + (content or "")

            # Write content to file
            mode = 'a+' if append else 'w'
            with open(full_path, mode, encoding="utf8") as file:
                file.write(content or "")

            # Optionally print status message
            if not is_quiet:
                print(f"Wrote to '{full_path}'")

            return True
        except (OSError, IOError) as error:
            self.log(f"write_file: {error}", level="error")
            return False

    def export(self):
        """
        Exports all data in MongoDB to JSON
        """
        cache = self.update_cache()

        path_export = pathlib.Path('~/.cabinet/export').expanduser()

        # Create the directory if it doesn't exist
        if not path_export.exists():
            path_export.mkdir(parents=True)

        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        file_name = f"cabinet export {formatted_datetime}"

        with open(path_export / file_name, 'w', encoding='utf-8') as file:
            file.write(cache or '')

        self.log(f"Exported to {path_export / file_name}")

def main():
    """
    Main function for running Cabinet.

    Args:
        None

    Returns:
        None

    Usage:
        (from the terminal)
        cabinet --configure
        cabinet edit <file path/name, optional; default: edit entire MongoDB>
    """

    cab = Cabinet()

    class ValidatePutArgs(argparse.Action):
        """
        Custom argparse action to validate the number of arguments for the --put option.
        Ensures that a minimum of 2 arguments are provided.
        """

        def __call__(self, parser, namespace, values, option_string=None):
            if not values or len(values) < 2:
                if values and len(values) == 1 and values[0] == 'ut':
                    print("I think you meant to use '--put' or '-p'.\n")
                parser.error(
                    f"At least 2 arguments are required for {option_string}")
            setattr(namespace, self.dest, values)

    parser = argparse.ArgumentParser(
        description=f"Cabinet ({version})")

    parser.add_argument('--configure', '-config', dest='configure',
                        action='store_true', help='Configure')
    parser.add_argument('--edit', '-e', dest='edit', action='store_true',
                        help='Edit Cabinet\'s MongoDB as a JSON file')
    parser.add_argument('--edit-file', '-ef', type=str, dest='edit_file',
                        help='Edit a specific file')
    parser.add_argument('--force-cache-update', dest='force_cache_update', action='store_true',
                    help='Disable using the cache for MongoDB queries')
    parser.add_argument('--no-create', dest='create',
                        action='store_false',
                        help='(for -ef) Do not create file if it does not exist')
    parser.add_argument('--get', '-g', dest='get', nargs='+',
                        help='Get a property from MongoDB')
    parser.add_argument('--put', '-p', dest='put', nargs='+', action=ValidatePutArgs,
                        help='Put a property into MongoDB')
    parser.add_argument('--remove', '-rm', dest='remove',
                        nargs='+', help='Remove a property from MongoDB')
    parser.add_argument('--get-file', dest='get_file',
                        type=str, help='Get file')
    parser.add_argument('--export', dest='export', action='store_true',
                        help='Exports MongoDB to ~/.cabinet/export')
    parser.add_argument('--strip', dest='strip', action='store_false',
                        help='(for --get-file) Whether to strip file content whitespace')
    parser.add_argument('--log', '-l', type=str,
                        dest='log', help='Log a message to the default location')
    parser.add_argument('--logdb', '-ldb', type=str,
                        dest='logdb', help='Log a message to MongoDB')
    parser.add_argument('--level', type=str, dest='log_level',
                        help='(for -l) Log level [debug, info, warn, error, critical]')
    parser.add_argument('--editor', type=str, dest='editor',
                        help='(for --edit and --edit-file) Specify an editor to use')
    parser.add_argument('--db-name', type=str, dest='db_name',
                        help='(for --logdb) Specify a database name')
    parser.add_argument('--cluster-name', type=str, dest='cluster_name',
                        help='(for --logdb) Specify a cluster name')

    mail_group = parser.add_argument_group('Mail')
    mail_group.add_argument(
        '--mail', dest='mail', action='store_true', help='Sends an email')
    mail_group.add_argument(
        '--subject', '-s', dest='subject', required='--mail' in sys.argv, help='Email subject')
    mail_group.add_argument(
        '--body', '-b', dest='body', required='--mail' in sys.argv, help='Email body')
    mail_group.add_argument('--to', '-t', dest='to_addr',
                            help='The "to" email address')

    parser.add_argument('-v', '--version', action='version',
                        help='Display the version of Cabinet', version=version('cabinet'))

    args = parser.parse_args()

    if args.configure:
        cab.config()
    elif args.edit:
        cab.edit_cabinet(editor=args.editor)
    elif args.edit_file:
        cab.edit_file(file_path=args.edit_file,
                      create_if_not_exist=args.create,
                      editor=args.editor)
    elif args.get:
        cab.get(is_print=True, warn_missing=True,
                force_cache_update=args.force_cache_update, *args.get)
    elif args.put:
        attribute_values = args.put
        cab.put(*attribute_values, is_print=True)
    elif args.remove:
        attribute_values = args.remove
        cab.remove(*attribute_values, is_print=True)
    elif args.get_file:
        cab.get_file_as_array(file_name=args.get_file,
                              file_path='', strip=args.strip)
    elif args.log:
        cab.log(message=args.log, level=args.log_level)
    elif args.logdb:
        cab.logdb(message=args.logdb, level=args.log_level,
                  db_name=args.db_name, cluster_name=args.cluster_name)
    elif args.export:
        cab.export()
    elif args.mail:
        to_addr = None
        if args.to_addr:
            to_addr = ''.join(args.to_addr).split(',')
        Mail().send(args.subject, args.body, to_addr=to_addr)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
