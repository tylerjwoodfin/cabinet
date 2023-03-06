"""
The main module for file management
"""

import os
import json
import pathlib
import logging
import sys
from datetime import date

IS_INITIALIZED = False

def main():
    """
    Loads the settings.json file
    """

    global PATH_CABINET
    global PATH_LOG
    global PATH_CONFIG_FILE
    global SETTINGS
    global PULL_COMMAND
    global PUSH_COMMAND
    global IS_INITIALIZED
    SETTINGS = None

    if IS_INITIALIZED:
        return

    # config file, stored within the package
    PATH_CONFIG_FILE = f'{pathlib.Path(__file__).resolve().parent}/config.json'

    # Determines where settings.json is stored; by default, this is ~/cabinet
    PATH_CABINET = os.path.expanduser(
        get_config('path_cabinet'))

    if not PATH_CABINET:
        path_cabinet_msg = """Enter the directory to store settings.json.\n"""\
            f"""This should be a public place, """\
            f"""such as {pathlib.Path.home().resolve()}/cabinet.\n\n"""
        PATH_CABINET = input(path_cabinet_msg)

    try:
        with open(f'{PATH_CABINET}/settings.json', 'r+') as file:
            file.seek(0, os.SEEK_END)
    except:
        # initialize settings file if it doesn't exist
        if not os.path.exists(PATH_CABINET):
            os.makedirs(PATH_CABINET)
        with open(f'{PATH_CABINET}/settings.json', 'x+') as file:
            print(
                f"\n\nWarning: settings.json not found; created a blank one in {PATH_CABINET}")
            print("You can change this location by calling 'cabinet config'.\n\n")
            file.write('{}')

    try:
        SETTINGS = json.load(open(f'{PATH_CABINET}/settings.json'))
    except json.decoder.JSONDecodeError as e:
        response = input(
            f"The settings file ({PATH_CABINET}/settings.json) is not valid JSON. Do you want to replace it with an empty JSON file? (The existing file will be backed up in {PATH_CABINET}) (y/n)\n")
        if response.lower().startswith("y"):
            print("Backing up...")

            # for some reason, this only works when you call touch; TODO fix this
            os.system(
                f"touch {PATH_CABINET}/settings-backup.json && cp {PATH_CABINET}/settings.json {PATH_CABINET}/settings-backup.json")
            print(f"Backed up to {PATH_CABINET}/settings-backup.json")
            with open(f'{PATH_CABINET}/settings.json', 'w+') as file:
                file.write('{}')
            print("Done. Please try your last command again.")
        else:
            print(
                f"OK. Please fix {PATH_CABINET}/settings.json and try again.")

        sys.exit(-1)

    PATH_LOG = get('path', 'log')
    if PATH_LOG == None:
        PATH_LOG = put(
            'path', 'log', f"{PATH_CABINET}/log", fileName='settings.json')
        print(
            f"\n\nCalling cabinet.log in Python will now write to {PATH_CABINET}/log by default.")
        print(f"You can change this in {PATH_CABINET}/settings.json.\n\n")
    if not os.path.exists(PATH_LOG):
        os.makedirs(PATH_LOG)
    if not PATH_LOG[-1] == '/':
        PATH_LOG += '/'

    IS_INITIALIZED = True

def edit(path, create_if_not_exist=False):
    """
    Edit and save a file using Vim
    Allows for shortcuts by setting paths in settings.json -> path -> edit
    """
    # allows for shortcuts by setting paths in settings.json -> path -> edit
    if path in get("path", "edit"):
        item = get("path", "edit", path)
        if isinstance(item) != dict or "value" not in item.keys():
            log(
                f"Could not use shortcut for {path} in getItem(path -> edit); should be a JSON object with value", level="warn")
        else:
            path = item["value"]

    if not create_if_not_exist and not os.path.exists(path):
        print(f"File does not exist: {path}")
        return -1

    # cache original file to check for differences
    file_contents = []
    file_path = '/'.join(path.split("/")[:-1])
    file_name = path.split("/")[-1]
    if os.path.exists(path):
        file_contents = get_file_as_array(
            file_name, file_path=file_path)

    os.system(f"vim {path}")

    if get_file_as_array(file_name, file_path=file_path) == file_contents:
        print("No changes.")


def get(*attribute, warn=False):
    """
    Returns a property in settings.json.
    Usage: get('person', 'name')
    """

    if SETTINGS is None:
        return None

    _settings = SETTINGS

    for index, item in enumerate(attribute):
        if item in _settings:
            _settings = _settings[item]
        elif warn and (len(attribute) < 2 or attribute[1] != "edit"):
            print(
                f"Warning: {item} not found in {_settings if index > 0 else f'{PATH_CABINET}/settings.json'}")
            return None
        else:
            return None

    return _settings

def put(*attribute, value=None, fileName='settings.json'):
    """
    Sets a property in settings.json (or some other `fileName`).
    Usage: set('person', 'name', 'Tyler')
    The last argument is the value to set, unless value is specified.
    Returns the value set.
    """
    
    path_full = f"{PATH_CABINET}/{fileName}"

    if not value:
        value = attribute[-1]

    _settings = SETTINGS if fileName == 'settings.json' else json.load(
        open(path_full))

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

    with open(path_full, 'w+') as file:
        json.dump(_settings, file, indent=4)

    return value


def get_file_as_array(item, file_path=None, strip=True, ignore_not_found=False):
    """
    Returns the file as an array; strips using strip() unless strip is set to False
    """

    if file_path is None:
        file_path = PATH_LOG
    elif file_path == "notes":
        file_path = get('path', 'notes', 'local')

        if not file_path[-1] == '/':
            file_path += '/'

    try:

        if not file_path[-1] == '/':
            file_path += '/'

        content = open(file_path + item, "r").read()

        if strip is not False:
            content = content.strip()

        return content.split('\n')
    except Exception as error:
        if not ignore_not_found or error.__class__ != FileNotFoundError:
            log(f"getFileAsArray: {error}", level="error")
        return ""


def write_file(file_name, file_path=None, content=None, append=False, is_quiet=False):
    """
    Writes a file to the specified path and creates subfolders if necessary
    """

    if file_path is None:
        file_path = PATH_LOG[0:-1] if PATH_LOG.endswith("/") else PATH_LOG
    elif file_path == "notes":
        file_path = get('path', 'notes', 'local')

    if content is None:
        content = ""

    if not os.path.exists(file_path):
        os.makedirs(file_path)

    with open(file_path + "/" + file_name, 'w+' if not append else 'a+') as file:
        file.write(content)

        if not is_quiet:
            print(f"Wrote to '{file_path}/{file_name}'")


def get_config(key=None):
    """
    Gets a property from the internal configuration file
    """

    try:
        with open(PATH_CONFIG_FILE, 'r+') as file:
            return json.load(file)[key]
    except FileNotFoundError:
        if key == 'path_cabinet':
            # set default settings.json and log path to ~/cabinet
            path_cabinet_msg = """Enter the directory to store settings.json.\n"""\
                f"""This should be a public place, """\
                f"""such as {pathlib.Path.home().resolve()}/cabinet.\n\n"""

            PATH_CABINET = input(path_cabinet_msg)
            put_config(key, PATH_CABINET)
            return PATH_CABINET
    except KeyError:
        print(f"Warning: Key error for key: {key}")
        return ""
    except json.decoder.JSONDecodeError:
        response = input(
            f"The config file ({PATH_CONFIG_FILE}) is not valid JSON. Do you want to replace it with an empty JSON file?  (you will lose existing data) (y/n)\n")
        if response.lower().startswith("y"):
            with open(PATH_CONFIG_FILE, 'w+') as f:
                f.write('{}')
            print("Done. Please try your last command again.")
        else:
            print(f"OK. Please fix {PATH_CONFIG_FILE} and try again.")

        sys.exit(-1)


def put_config(key=None, value=None):
    """
    Updates the internal configuration file
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
            print("Warning: using tilde expansions may cause problems if using cabinet for multiple users. It is recommended to use full paths.")

    try:
        with open(PATH_CONFIG_FILE, 'r+') as file:
            config = json.load(file)
    except FileNotFoundError:
        with open(PATH_CONFIG_FILE, 'x+') as f:
            print(f"Note: Could not find an existing config file... creating a new one.")
            f.write('{}')
            config = {}

    config[key] = value

    with open(PATH_CONFIG_FILE, 'w+') as file:
        json.dump(config, file, indent=4)

    print(f"\n\nUpdated configuration file ({PATH_CONFIG_FILE}).")
    print(f"{key} is now {value}\n")

    return value


def get_logger(log_name=None, level=logging.INFO, file_path=None, is_quiet=False):
    """
    Returns a custom logger with the given name and level
    """

    today = str(date.today())

    if file_path is None:
        file_path = f"{PATH_LOG}{today}"
    if log_name is None:
        log_name = f"LOG_DAILY {today}"

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

    file_handler = logging.FileHandler(f"{file_path}/{log_name}.log", mode='a')
    file_handler.setFormatter(log_format)

    logger.addHandler(file_handler)
    return logger


def log(message=None, log_name=None, level="info", file_path=None, is_quiet=False):
    """
    Logs a message
    """

    if message is None:
        message = ""

    if level is None or level == "info":
        logger = get_logger(
            log_name=log_name, level=logging.INFO, file_path=file_path, is_quiet=is_quiet)
        logger.info(message)
    elif level == "debug":
        logger = get_logger(
            log_name=log_name, level=logging.DEBUG, file_path=file_path, is_quiet=is_quiet)
        logger.debug(message)
    elif level == "warn" or level == "warning":
        logger = get_logger(
            log_name=log_name, level=logging.WARN, file_path=file_path, is_quiet=is_quiet)
        logger.warning(message)
    elif level == "error":
        logger = get_logger(
            log_name=log_name, level=logging.ERROR, file_path=file_path, is_quiet=is_quiet)
        logger.error(message)
    elif level == "critical":
        logger = get_logger(
            log_name=log_name, level=logging.CRITICAL, file_path=file_path, is_quiet=is_quiet)
        logger.critical(message)
    else:
        logger = get_logger(
            log_name=log_name, level=logging.ERROR, file_path=file_path, is_quiet=is_quiet)
        logger.error(f"Unknown log level: {level}; using ERROR")
        logger.error(message)


# Initialize
main()

if __name__ == "__main__":
    print("Cabinet is a library not intended to be directly run. See README.md.")

if "cabinet" in sys.argv[0] and len(sys.argv) > 1:
    if sys.argv[-1] == 'config':
        put_config('path_cabinet', input(
            f"Enter the full path of the directory where you want to store all data (currently {PATH_CABINET}):\n"))

    if sys.argv[1] == 'edit':
        if len(sys.argv) > 2:
            edit(sys.argv[2])
        else:
            edit(f"{PATH_CABINET}/settings.json")
