"""
Cabinet provides a simple interface for storing and retrieving data in a centralized location. 

It includes a variety of utility methods for managing files, logging, and managing configurations.

Usage:
    ```
    from cabinet import Cabinet

    cab = Cabinet()
    ```
"""

import os
import json
import pathlib
import logging
import sys
from datetime import date
from typing import Optional


class Cabinet:
    """
    The main class for Cabinet
    """

    path_cabinet: str = None
    path_config_file: str = None
    path_settings_file: str = None
    path_log: str = None
    settings_json = None

    def __init__(self, path_cabinet: str = None):
        """
        The main module for file management

        Args:
            - path_cabinet (str, optional): the directory of a settings.json file to be used
                Defaults to ~/cabinet if unset

        Returns:
            None

        Usage:
            ```
            from cabinet import Cabinet
            cab = cabinet.Cabinet()
            ```
        """

        # config file, stored within the package
        self.path_config_file = pathlib.Path(
            __file__).resolve().parent / "config.json"

        # Determines where settings.json is stored; by default, this is ~/cabinet
        self.path_cabinet = os.path.expanduser(
            self._get_config('path_cabinet'))

        path_cabinet = path_cabinet or self.path_cabinet

        if path_cabinet is None:
            path_cabinet = input(
                "Enter the directory to store settings.json: ")
            if not path_cabinet:
                path_cabinet = str(pathlib.Path.home() / "cabinet")

        self.path_settings_file = pathlib.Path(path_cabinet) / "settings.json"

        try:
            with open(f'{path_cabinet}/settings.json', 'r+', encoding="utf8") as file:
                file.seek(0, os.SEEK_END)
        except FileNotFoundError as error:
            # initialize settings file if it doesn't exist
            if not os.path.exists(path_cabinet):
                os.makedirs(path_cabinet)
            with open(f'{path_cabinet}/settings.json', 'x+', encoding="utf8") as file:
                print(f"\n\nWarning: settings.json not found; \
                    created a blank one in {path_cabinet} ({error})")
                print("You can change this location by calling 'cabinet config'.\n\n")
                file.write('{}')

        try:
            self.settings_json = json.load(
                open(f'{path_cabinet}/settings.json', encoding="utf8"))

        except json.decoder.JSONDecodeError as error:
            print(f"{error}\n")

            response = input(
                f"The settings file ({path_cabinet}/settings.json) is not valid JSON. \
                    Do you want to replace it with an empty JSON file? \
                        (The existing file will be backed up in {path_cabinet}) (y/n)\n")
            if response.lower().startswith("y"):
                print("Backing up...")

                # for some reason, this only works when you call touch; TODO fix this
                os.system(
                    f"touch {path_cabinet}/settings-backup.json \
                        && cp {path_cabinet}/settings.json {path_cabinet}/settings-backup.json")
                print(f"Backed up to {path_cabinet}/settings-backup.json")
                with open(f'{path_cabinet}/settings.json', 'w+', encoding="utf8") as file:
                    file.write('{}')
                print("Done. Please try your last command again.")
            else:
                print(
                    f"OK. Please fix {path_cabinet}/settings.json and try again.")

            sys.exit(-1)

        path_log = self.get('path', 'log')

        if path_log is None:
            path_log = self.put(
                'path', 'log', f"{path_cabinet}/log", file_name='settings.json')
            print(f"""
                \n\nCalling cabinet.log in Python will now write to {path_cabinet}/log by default.
                """)
            print(f"You can change this in {path_cabinet}/settings.json.\n\n")
        if not os.path.exists(path_log):
            os.makedirs(path_log)
        if not path_log[-1] == '/':
            path_log += '/'

        self.path_log = path_log

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
            if key == 'path_cabinet':
                # set default settings.json and log path to ~/cabinet
                path_cabinet_msg = """Enter the directory to store settings.json.\n"""\
                    f"""This should be a public place, """\
                    f"""such as {pathlib.Path.home().resolve()}/cabinet.\n\n"""

                path_cabinet = input(path_cabinet_msg)

                self._put_config(key, path_cabinet)
                return path_cabinet
        except KeyError:
            print(f"Warning: Key error for key: {key}")
            return ""
        except json.decoder.JSONDecodeError:
            response = input(
                f"The config file ({self.path_config_file}) is not valid JSON. Do you want to \
                    replace it with an empty JSON file?  (you will lose existing data) (y/n)\n")
            if response.lower().startswith("y"):
                with open(self.path_config_file, 'w+', encoding="utf8") as file:
                    file.write('{}')
                print("Done. Please try your last command again.")
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
        else:

            # error correction
            if key == 'path_cabinet' and value[0] != '/' and value[0] != '~':
                value = f"/{value}"
            if key == 'path_cabinet' and value[-1] == '/':
                value = f"{value[:-1]}"

            # warn about potential problems
            if not os.path.exists(os.path.expanduser(value)):
                print(f"Warning: {value} is not a valid path.")
            if value[0] == '~':
                print("""
Warning: using tilde expansions may cause problems
if using cabinet for multiple users. It is recommended to use full paths.""")

        try:
            with open(self.path_config_file, 'r+', encoding="utf8") as file:
                config = json.load(file)
        except FileNotFoundError:
            with open(self.path_config_file, 'x+', encoding="utf8") as file:
                print(
                    "Note: Could not find an existing config file; creating a new one.")
                file.write('{}')
                config = {}

        config[key] = value

        with open(self.path_config_file, 'w+', encoding="utf8") as file:
            json.dump(config, file, indent=4)

        print(f"\n\nUpdated configuration file ({self.path_config_file}).")
        print(f"{key} is now {value}\n")

        return value

    def _get_logger(self, log_name: str = None, level: int = logging.INFO,
                    file_path: str = None, is_quiet: bool = False) -> logging.Logger:
        """
        A helper function for log()

        Returns a customized logger object with the specified name and level,
        and optionally logs to a file.

        Args:
        - log_name (str): the name of the logger (defaults to 'root')
        - level (int): the logging level to use (defaults to logging.INFO)
        - file_path (str): the path to a file to log to
            (defaults to None, meaning log only to console)
        - is_quiet (bool): if True, only logs to file and not to console (defaults to False)

        Returns:
        - logger (Logger): the configured logger object
        """

        today = str(date.today())

        if file_path is None:
            file_path = f"{self.path_log}{today}"
        if log_name is None:
            log_name = f"LOG_DAILY_{today}"

        # create path if necessary
        if not os.path.exists(file_path):
            print(f"Creating {file_path}")
            os.makedirs(file_path)

        logger = logging.getLogger(log_name)

        logger.setLevel(level)

        if logger.handlers:
            logger.handlers = []

        format_string = "%(asctime)s — %(levelname)s — %(message)s"
        log_format = logging.Formatter(format_string)

        if not is_quiet:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(log_format)
            logger.addHandler(console_handler)

        file_handler = logging.FileHandler(
            f"{file_path}/{log_name}.log", mode='a')
        file_handler.setFormatter(log_format)

        logger.addHandler(file_handler)
        return logger

    def configure(self):
        """
        Configures the Cabinet instance based on command line arguments or user input.
        """

        message = f"""
Enter the full path of the directory where you want to store 
all data (currently {self.path_cabinet}):\n"""

        self._put_config('path_cabinet', input(message))

    def edit_file(self, file_path: str = None, create_if_not_exist: bool = True) -> None:
        """
        Edit and save a file using Vim.

        Args:
            - file_path (str, optional): The path to the file to edit. 
                Allows for shortcuts by setting paths in settings.json -> path -> edit
                If unset, edit settings.json

            - create_if_not_exist (bool, optional): Whether to create the file if it does not exist.
                Defaults to False.

        Raises:
            - ValueError: If the file_path is not a string.

            - FileNotFoundError: If the file does not exist and create_if_not_exist is True.

        Returns:
            None
        """

        # edit settings.json if no file_path
        if file_path is None:
            message = f"""
Enter the path of the file you want to edit
(default: {self.path_cabinet}/settings.json):\n"""

            path = self.path_settings_file or input(
                message) or f"{self.path_cabinet}/settings.json"
            self.edit_file(path)
            return

        # allows for shortcuts by setting paths in settings.json -> path -> edit
        if file_path in self.get("path", "edit"):
            item = self.get("path", "edit", file_path)
            if not isinstance(item, dict) or "value" not in item.keys():
                self.log(f"Could not use shortcut for {file_path} \
                    in getItem(path -> edit); should be a JSON object with value", level="warn")
            else:
                file_path = item["value"]

        if not os.path.exists(file_path):
            if create_if_not_exist:
                with open(file_path, "w", encoding="utf-8"):
                    pass
            else:
                self.log("Could not find file to edit", level="error")
                raise FileNotFoundError(f"File does not exist: {file_path}")

        # cache original file to check for differences
        with open(file_path, "r", encoding="utf-8") as file:
            original_contents = file.readlines()

        os.system(f"vim {file_path}")

        with open(file_path, "r", encoding="utf-8") as file:
            new_contents = file.readlines()

        if original_contents == new_contents:
            print("No changes.")

    def get(self, *attributes, warn_missing=False):
        """
        Returns a property in a JSON file based on the input attributes.

        Args:
            - attributes (str): the attributes to traverse in the JSON file
            - warn_missing (bool, optional): whether to warn if an attribute is missing

        Returns:
            - The value of the attribute if it exists in the JSON file, otherwise default.

        Usage:
            - get('person', 'tyler', 'salary') returns person -> tyler -> salary from self.settings
        """

        if self.settings_json is None:
            return None

        settings = self.settings_json

        for index, item in enumerate(attributes):
            if item in settings:
                settings = settings[item]
            elif warn_missing and (len(attributes) < 2 or attributes[1] != "edit"):
                print(
                    f"Warning: {item} not found in \
                        {settings if index > 0 else f'{self.path_cabinet}/settings.json'}")
                return None
            else:
                return None

        return settings

    def put(self, *attribute, value=None, file_name='settings.json'):
        """
        Adds or replaces a property in a JSON file (default name: settings.json).

        Args:
            *attribute (str): A series of keys in the JSON object
                to identify the location of the property.
            value (optional): The value to put into the property.
                If not specified, the last argument will be used.
            file_name (str): The name of the JSON file to put the property in.

        Returns:
            The value that was put into the property.
        """

        path_full = f"{self.path_cabinet}/{file_name}"

        if not value:
            value = attribute[-1]

        _settings = self.settings_json if file_name == 'settings.json' else json.load(
            open(path_full, encoding="utf8"))

        # iterate through entire JSON object and replace 2nd to last attribute with value

        partition = _settings
        for index, item in enumerate(attribute[:-1]):
            if item not in partition:
                partition[item] = value if index == len(attribute) - 2 else {}
                partition = partition[item]
                print(
                    f"Warning: Adding new key '{item}' to {partition if index > 0 else path_full}")
            else:
                if index == len(attribute) - 2:
                    partition[item] = value
                else:
                    partition = partition[item]

        with open(path_full, 'w+', encoding="utf8") as file:
            json.dump(_settings, file, indent=4)

        return value

    def get_file_as_array(self, item: str, file_path=None, strip: bool = True,
                          ignore_not_found: bool = False):
        """
        Reads a file and returns its contents as a list of lines.
        The file is assumed to be encoded in UTF-8.

        Args:
            - item (str): The filename to read.
            - file_path (str, optional): The path to the directory containing the file.
                If None, the default path is used.
            - strip (bool, optional): Whether to strip the lines of whitespace characters
                On by default.
            - ignore_not_found (bool, optional): Whether to return None when the file is not found.
                False by default.

        Returns:
            A list of lines, or None if the file is not found and ignore_not_found is True.
        """

        if file_path is None:
            file_path = self.path_log
        elif file_path == "notes":
            file_path = self.get('path', 'notes')

        if not file_path[-1] == '/':
            file_path += '/'

        try:
            content = open(file_path + item, "r", encoding="utf8").read()

            if strip:
                content = content.strip()

            return content.split('\n')
        except FileNotFoundError as error:
            if not ignore_not_found:
                self.log(f"get_file_as_array: {error}", level="error")
            return None

    def write_file(self, file_name: str, file_path: Optional[str] = None,
                   content: Optional[str] = None, append: bool = False,
                   is_quiet: bool = False) -> bool:
        """
        Writes a file to the specified path and creates subfolders if necessary.

        Args:
            - file_name (str): The name of the file to write.
            - file_path (str, optional): The path to the directory where the file should be written.
                If None, path_log is used.
            - content (str, optional): The contents to write to the file.
                If None, an empty file is created.
            - append (bool, optional): Whether to append to the file instead of overwriting it.
                Default: False
            - is_quiet (bool, optional): Whether to skip printing status messages.
                Default: False

        Return:
            True if the file was written successfully
            False otherwise.
        """

        try:
            if file_path is None:
                file_path = self.path_log.rstrip("/")
            elif file_path == "notes":
                file_path = self.get('path', 'notes')
            os.makedirs(file_path, exist_ok=True)
            with open(f"{file_path}/{file_name}", 'a+' if append else 'w', encoding="utf8") as file:
                file.write(content or "")
            if not is_quiet:
                print(f"Wrote to '{file_path}/{file_name}'")
            return True
        except (OSError, IOError) as error:
            self.log(f"write_file: {error}", level="error")
            return False

    def log(self, message: str = '', log_name: str = None, level: str = 'info',
            file_path: str = None, is_quiet: bool = False) -> None:
        """
        Logs a message using the specified log level
        and writes it to a file if a file path is provided.

        Args:
            message (str, optional): The message to log. Defaults to ''.
            log_name (str, optional): The name of the logger to use. Defaults to None.
            level (str, optional): The log level to use. 
                Must be one of 'debug', 'info', 'warning', 'error', or 'critical'.
                Defaults to 'info'.
            file_path (str, optional): The path to the log file. 
                If not provided, logs will be saved to settings.json -> path -> log.
                Defaults to None.
            is_quiet (bool, optional): If True, logging output will be silenced. Defaults to False.

        Raises:
            ValueError: If an invalid log level is provided.

        Returns:
            None
        """

        # validate log level
        valid_levels = {'debug', 'info', 'warn',
                        'warning', 'error', 'critical'}
        if level.lower() not in valid_levels:
            raise ValueError(
                f"Invalid log level: {level}. Must be one of {', '.join(valid_levels)}.")

        # get logger instance
        logger = self._get_logger(log_name=log_name, level=level.upper(),
                                  file_path=file_path, is_quiet=is_quiet)

        # Log message
        if not is_quiet:
            getattr(logger, level.lower())(message)


def main():
    """
    Main function for running Cabinet.

    Args:
        None

    Returns:
        None

    Usage:
        (from the terminal)
        cabinet config
        cabinet edit <file path/name, optional; default: settings.json>
    """

    if len(sys.argv) < 2:
        print("Cabinet is not intended to be directly run. See README.md.")
        sys.exit(0)

    if "cabinet" in sys.argv[0] and len(sys.argv) > 1:
        if "config" == sys.argv[1]:
            Cabinet().configure()
        elif "edit" == sys.argv[1]:
            path = None if len(sys.argv) < 3 else sys.argv[2]
            Cabinet().edit_file(path)


if __name__ == "__main__":
    main()
