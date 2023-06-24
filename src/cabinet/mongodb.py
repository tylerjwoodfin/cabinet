"""
A MongoDB Experiment
"""
import os
import ast
import sys
import json
import pathlib
import getpass
import subprocess
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from .constants import (
    NEW_SETUP_MSG_INTRO,
    NEW_SETUP_MSG_MONGODB_INSTRUCTIONS,
    CONFIG_MONGODB_USERNAME,
    CONFIG_MONGODB_PASSWORD,
    CONFIG_MONGODB_CLUSTER_NAME,
    CONFIG_MONGODB_DB_NAME,
    ERROR_CONFIG_FILE_NOT_FOUND,
    ERROR_CONFIG_MISSING_VALUES,
    ERROR_CONFIG_JSON_DECODE
)


class Cabinet:
    """
    Cabinet class
    """

    mongodb_username: str = ''
    mongodb_password: str = ''
    mongodb_cluster_name: str = ''
    mongodb_db_name: str = ''
    mongodb_uri = ""
    client: MongoClient = None
    database = None
    new_setup: bool = False
    path_config_file = str(pathlib.Path(
        __file__).resolve().parent / "cabinet_config.json")

    def _get_config(self, key=None):
        """
        Gets a property from the internal configuration file.

        Args:
        - key (str): The key to search for in the JSON file.

        Returns:
        - The value of the key in the JSON file.

        If the JSON file does not exist or is not valid JSON,
            the function provides default behavior:
        - If `key` is `path_cabinet`, the function prompts
            the user to enter a directory to store settings.json.
        - If `key` is not found, the function returns an empty string.
        - If the file is not valid JSON, the function prompts
            the user to replace the file with an empty JSON file.
        """

        try:
            with open(self.path_config_file, 'r+', encoding="utf8") as file:
                return json.load(file)[key]
        except FileNotFoundError:
            if key == 'mongodb_username':
                # setup
                self.new_setup = True
                has_mongodb = input(NEW_SETUP_MSG_INTRO)

                value = ''
                if has_mongodb.lower().startswith('y'):
                    value = input(CONFIG_MONGODB_USERNAME)
                else:
                    input(NEW_SETUP_MSG_MONGODB_INSTRUCTIONS)
                    value = input(CONFIG_MONGODB_USERNAME)

                self._put_config(key, value)
                return value
            else:
                print(f"{ERROR_CONFIG_FILE_NOT_FOUND}\n")
        except KeyError:
            if self.new_setup:
                if key == 'mongodb_password':
                    value = getpass.getpass(CONFIG_MONGODB_PASSWORD)
                    self._put_config(key, value)
                if key == 'mongodb_cluster_name':
                    value = input(CONFIG_MONGODB_CLUSTER_NAME)
                    self._put_config(key, value)
                if key == 'mongodb_db_name':
                    value = input(CONFIG_MONGODB_DB_NAME)
                    self._put_config(key, value)
                return value
            else:
                print(
                    f"Warning: Could not find {key} in {self.path_config_file}")
            return ""
        except json.decoder.JSONDecodeError:
            err_msg = f"Problem reading {self.path_config_file}.\n\n{ERROR_CONFIG_JSON_DECODE}"
            response = input(err_msg)

            if response.lower().startswith("y"):
                with open(self.path_config_file, 'w+', encoding="utf8") as file:
                    file.write('{}')
                print("Done. Please try again.")
            else:
                print(f"OK. Please fix {self.path_config_file} and try again.")

            sys.exit(-1)

    def _put_config(self, key: str = None, value: str = None):
        """
        Updates the internal configuration file with a new key-value pair.

        Args:
            key (str): The key for the configuration setting.
            value (str): The value for the configuration setting.

        Returns:
            str: The updated value for the configuration setting.

        Raises:
            FileNotFoundError: If the configuration file cannot be found.
        """

        if value == "":
            print("No changes were made.")
            sys.exit(1)

        try:
            with open(self.path_config_file, 'r+', encoding="utf8") as file:
                config = json.load(file)
        except FileNotFoundError:
            with open(self.path_config_file, 'x+', encoding="utf8") as file:
                self._ifprint(
                    "Note: Could not find an existing config file; creating a new one.",
                    self.new_setup is False)
                file.write('{}')
                config = {}

        config[key] = value

        with open(self.path_config_file, 'w+', encoding="utf8") as file:
            json.dump(config, file, indent=4)

        print(f"\nUpdated configuration file ({self.path_config_file}).")
        self._ifprint(f"{key} is now {value}\n", self.new_setup is False)

        return value

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

    def __init__(self):
        """
        The main module for file management
        """

        # these should match class attributes above
        keys = ["mongodb_username", "mongodb_password",
                "mongodb_cluster_name", "mongodb_db_name"]

        for key in keys:
            value = self._get_config(key)
            setattr(self, key, value)

        if any(getattr(self, key) is None or getattr(self, key) == '' for key in keys):
            # one or more values missing
            print(self.mongodb_username)
            print(self.mongodb_password)
            print(self.mongodb_cluster_name)
            print(self.mongodb_db_name)
            input(ERROR_CONFIG_MISSING_VALUES)
            self.config()

        self.new_setup = False
        self.uri = (f"mongodb+srv://{self.mongodb_username}:{self.mongodb_password}"
                    f"@{self.mongodb_cluster_name}.1jxchnk.mongodb.net/"
                    f"{self.mongodb_db_name}?retryWrites=true&w=majority")
        self.client = MongoClient(self.uri, server_api=ServerApi('1'))
        self.database = self.client.cabinet

    def config(self):
        """
        Config
        """

        if os.isatty(sys.stdin.fileno()):
            # User is in a terminal, open with default editor
            try:
                subprocess.run(
                    [os.environ.get('EDITOR', 'vi'), self.path_config_file], check=True)
            except FileNotFoundError:
                print("Default editor not found. Unable to open the file.")
        else:
            if sys.platform.startswith('win32'):
                # Windows
                subprocess.run(
                    ['start', '', self.path_config_file], shell=True, check=True)
            elif sys.platform.startswith('darwin'):
                # macOS
                subprocess.run(['open', self.path_config_file], check=True)
            elif sys.platform.startswith('linux'):
                # Linux
                subprocess.run(['xdg-open', self.path_config_file], check=True)
            else:
                print(f"Please edit ${self.path_config_file} to configure.")

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

    def put(self, *attribute, value=None):
        """
        Adds or replaces a property
        """

        def parse_arg(value):
            """
            Infer the value type (e.g. 2 will not be parsed as a string)
            """
            if value == "null":
                return None
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    if value.lower() == 'true':
                        return True
                    if value.lower() == 'false':
                        return False
                    try:
                        return ast.literal_eval(value)
                    except (SyntaxError, ValueError):
                        return value

        custom_filter = {}

        if value is None:  # Check if value argument is None
            value = parse_arg(attribute[-1])

        cache = attribute[-1]
        json_structure = {}
        for item in reversed(attribute[:-1]):
            try:
                json_structure = {}
                json_structure[item] = cache
                cache = json_structure
            except TypeError as error:
                print(error)

        existing_data = self.database.cabinet.find_one({}, {"_id": 0})

        # Merge the new data with the existing data
        update = {"$set": {}}

        if len(attribute) > 2:
            update["$set"][attribute[0]] = self.merge_nested_data(existing_data.get(
                attribute[0], {}), json_structure[attribute[0]])
        else:
            update = {"$set": json_structure}

        result = self.database.cabinet.update_many(custom_filter, update)

        print(f"Modified {result.modified_count} item(s)")
        print(
            f"{' -> '.join(attribute[:-1])} set to {value}\n")

        return value

    def get(self, *attributes, warn_missing=False, is_print=False):
        """
        Returns a property from MongoDB based on the input attributes.

        Args:
            - attributes (str): the attributes check in MongoDB
            - warn_missing (bool, optional): whether to warn if an attribute is missing
            - is_print (bool, optional): whether to print the return value

        Returns:
            - The value of the attribute if it exists in MongoDB, otherwise default.

        Usage:
            - get('person', 'tyler', 'salary') returns person -> tyler -> salary from self.db
        """

        collection = self.database.cabinet

        document = collection.find_one(
            {}, {attribute: 1 for attribute in attributes})

        if document:
            result = document
            for attribute in attributes:
                if attribute in result:
                    result = result[attribute]
                else:
                    if warn_missing:
                        print(
                            f"Warning: Attribute '{attribute}' is missing in MongoDB")
                    return None
        else:
            if warn_missing:
                print("Warning: No document found in MongoDB")
            return None

        if is_print:
            print(result)

        return result

    def ping(self, is_print: bool = False):
        """
        Send a ping to verify successful connection
        """
        try:
            self.client.admin.command('ping')
            self._ifprint("Ping Successful", is_print)
            return True
        except Exception as error:
            print(error)
            return False

    def export(self):
        """
        Exports all data to JSON
        """
        data = self.database.cabinet.find_one({}, {"_id": 0})
        json_data = json.dumps(data, indent=4)

        with open('database.json', 'w', encoding='utf-8') as file:
            file.write(json_data)


cab = Cabinet()

print(cab.get('path'))
# cab.export()
