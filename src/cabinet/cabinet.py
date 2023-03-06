import os
import json
import pathlib
import logging
import sys
from datetime import date

IS_INITIALIZED = False

def main():
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
        getConfigItem('path_cabinet'))

    if not PATH_CABINET:
        path_cabinet_msg = """Enter the directory to store settings.json.\n"""\
            f"""This should be a public place, """\
            f"""such as {pathlib.Path.home().resolve()}/cabinet.\n\n"""
        PATH_CABINET = input(path_cabinet_msg)

    try:
        with open(f'{PATH_CABINET}/settings.json', 'r+') as f:
            f.seek(0, os.SEEK_END)
    except:
        # initialize settings file if it doesn't exist
        if not os.path.exists(PATH_CABINET):
            os.makedirs(PATH_CABINET)
        with open(f'{PATH_CABINET}/settings.json', 'x+') as f:
            print(
                f"\n\nWarning: settings.json not found; created a blank one in {PATH_CABINET}")
            print("You can change this location by calling 'cabinet config'.\n\n")
            f.write('{}')

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
            with open(f'{PATH_CABINET}/settings.json', 'w+') as f:
                f.write('{}')
            print("Done. Please try your last command again.")
        else:
            print(
                f"OK. Please fix {PATH_CABINET}/settings.json and try again.")

        sys.exit(-1)

    PATH_LOG = getItem('path', 'log')
    if PATH_LOG == None:
        PATH_LOG = setItem(
            'path', 'log', f"{PATH_CABINET}/log", fileName='settings.json')
        print(
            f"\n\nCalling cabinet.log in Python will now write to {PATH_CABINET}/log by default.")
        print(f"You can change this in {PATH_CABINET}/settings.json.\n\n")
    if not os.path.exists(PATH_LOG):
        os.makedirs(PATH_LOG)
    if not PATH_LOG[-1] == '/':
        PATH_LOG += '/'

    IS_INITIALIZED = True


"""
Pull from the cloud using the command of your choice.
"""


def pull():
    _sync = getItem("path", "cabinet")
    _sync_keys = _sync.keys()

    PULL_COMMAND = ''
    if 'sync-pull' in _sync_keys and 'sync-push' in _sync_keys:
        PULL_COMMAND = _sync['sync-pull']

    if PULL_COMMAND:
        print(f"Pulling {PATH_CABINET}/settings.json from cloud...")
        os.system(PULL_COMMAND)
        print("Pulled.")
        SETTINGS = json.load(open(f'{PATH_CABINET}/settings.json'))


"""
Edit and save a file using Vim
Allows for shortcuts by setting paths in settings.json -> path -> edit
settings.json -> path -> edit -> sync is reserved for the command to be run to sync files
"""


def editFile(path, sync=False, createIfNotExist=False):
    # allows for shortcuts by setting paths in settings.json -> path -> edit
    if path in getItem("path", "edit"):
        item = getItem("path", "edit", path)
        if isinstance(item) != dict or "value" not in item.keys():
            log(
                f"Could not use shortcut for {path} in getItem(path -> edit); should be a JSON object with value, sync attributes", level="warn")
        else:
            path = item["value"]
            sync = ("sync" in item.keys() and item["sync"]) or False

    pull_command = getItem("path", "edit", "sync-pull")
    if pull_command and sync:
        print(f"Pulling {path} from cloud...")
        os.system(pull_command)
        print("Pulled.")

    if not createIfNotExist and not os.path.exists(path):
        print(f"File does not exist: {path}")
        return -1

    # cache original file to check for differences
    file_contents = []
    file_path = '/'.join(path.split("/")[:-1])
    file_name = path.split("/")[-1]
    if os.path.exists(path):
        file_contents = getFileAsArray(
            file_name, filePath=file_path)

    os.system(f"vim {path}")

    if getFileAsArray(file_name, filePath=file_path) == file_contents:
        print("No changes.")
        sync = False

    push_command = getItem("path", "edit", "sync-push")
    if push_command and sync:
        print(f"Saving {path} to cloud...")
        os.system(push_command)
        print("Saved.")


"""
Returns a property in settings.json.
Usage: get('person', 'name')
"""


def getItem(*attribute, warn=False, sync=False):

    if sync:
        pull()

    global SETTINGS

    if SETTINGS == None:
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


"""
Sets a property in settings.json (or some other `fileName`).
Usage: set('person', 'name', 'Tyler')
The last argument is the value to set, unless value is specified.
Returns the value set.
"""


def setItem(*attribute, value=None, fileName='settings.json', sync=False):

    global SETTINGS
    path_full = f"{PATH_CABINET}/{fileName}"

    if sync:
        pull()

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

    push_command = getItem("path", "cabinet", "sync-push")
    if push_command and sync:
        print(f"Pushing {PATH_CABINET}/settings.json to cloud...")
        os.system(push_command)
        print("Saved.")

    return value


def getFileAsArray(item, filePath=None, strip=True, ignoreNotFound=False):
    """
    Returns the file as an array; strips using strip() unless strip is set to False
    """

    global PATH_LOG
    if filePath == None:
        filePath = PATH_LOG
    elif filePath == "notes":
        filePath = getItem('path', 'notes', 'local')

        if not filePath[-1] == '/':
            filePath += '/'

        # pull from cloud
        if getItem('path', 'notes', 'cloud', warn=False):
            try:
                os.system(
                    f"rclone copy {getItem('path', 'notes', 'cloud')} {filePath}")
            except Exception as e:
                log(f"Could not pull Notes from cloud: {e}", level="error")

    try:

        if not filePath[-1] == '/':
            filePath += '/'

        content = open(filePath + item, "r").read()

        if strip is not False:
            content = content.strip()

        return content.split('\n')
    except Exception as e:
        if not ignoreNotFound or e.__class__ != FileNotFoundError:
            log(f"getFileAsArray: {e}", level="error")
        return ""


def writeFile(fileName, filePath=None, content=None, append=False, is_quiet=False):
    """
    Writes a file to the specified path and creates subfolders if necessary
    """

    global PATH_LOG
    _filePath = filePath

    if filePath == None:
        filePath = PATH_LOG[0:-1] if PATH_LOG.endswith("/") else PATH_LOG
    elif filePath == "notes":
        filePath = getItem('path', 'notes', 'local')

    if content == None:
        content = ""

    if not os.path.exists(filePath):
        os.makedirs(filePath)

    with open(filePath + "/" + fileName, 'w+' if not append else 'a+') as file:
        file.write(content)

        if not is_quiet:
            print(f"Wrote to '{filePath}/{fileName}'")

    # push to cloud
    if _filePath == "notes" and getItem('path', 'notes', 'cloud', warn=False):
        try:
            os.system(
                f"rclone copy {filePath} {getItem('path', 'notes', 'cloud')}")
        except Exception as e:
            log(f"Could not sync Notes to cloud: {e}", level="error")


def getConfigItem(key=None):
    global PATH_CONFIG_FILE

    try:
        with open(PATH_CONFIG_FILE, 'r+') as file:
            return json.load(file)[key]
    except FileNotFoundError as e:
        if key == 'path_cabinet':
            # set default settings.json and log path to ~/cabinet
            path_cabinet_msg = """Enter the directory to store settings.json.\n"""\
                f"""This should be a public place, """\
                f"""such as {pathlib.Path.home().resolve()}/cabinet.\n\n"""

            PATH_CABINET = input(path_cabinet_msg)
            setConfigItem(key, PATH_CABINET)
            return PATH_CABINET
    except KeyError:
        print(f"Warning: Key error for key: {key}")
        return ""
    except json.decoder.JSONDecodeError as e:
        response = input(
            f"The config file ({PATH_CONFIG_FILE}) is not valid JSON. Do you want to replace it with an empty JSON file?  (you will lose existing data) (y/n)\n")
        if response.lower().startswith("y"):
            with open(PATH_CONFIG_FILE, 'w+') as f:
                f.write('{}')
            print("Done. Please try your last command again.")
        else:
            print(f"OK. Please fix {PATH_CONFIG_FILE} and try again.")

        sys.exit(-1)


def setConfigItem(key=None, value=None):
    """
    Updates the internal configuration file
    """

    global PATH_CONFIG_FILE

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


def getLogger(logName=None, level=logging.INFO, filePath=None, is_quiet=False):
    """
    Returns a custom logger with the given name and level
    """

    today = str(date.today())

    if filePath == None:
        filePath = f"{PATH_LOG}{today}"
    if logName == None:
        logName = f"LOG_DAILY {today}"

    # create path if necessary
    if not os.path.exists(filePath):
        print(f"Creating {filePath}")
        os.makedirs(filePath)

    logger = logging.getLogger(logName)

    logger.setLevel(level)

    if logger.handlers:
        logger.handlers = []

    format_string = ("%(asctime)s — %(levelname)s — %(message)s")
    log_format = logging.Formatter(format_string)

    if not is_quiet:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)

    file_handler = logging.FileHandler(f"{filePath}/{logName}.log", mode='a')
    file_handler.setFormatter(log_format)

    logger.addHandler(file_handler)
    return logger


def log(message=None, logName=None, level="info", filePath=None, is_quiet=False):

    if message == None:
        message = ""

    if level == None or level == "info":
        logger = getLogger(
            logName=logName, level=logging.INFO, filePath=filePath, is_quiet=is_quiet)
        logger.info(message)
    elif level == "debug":
        logger = getLogger(
            logName=logName, level=logging.DEBUG, filePath=filePath, is_quiet=is_quiet)
        logger.debug(message)
    elif level == "warn" or level == "warning":
        logger = getLogger(
            logName=logName, level=logging.WARN, filePath=filePath, is_quiet=is_quiet)
        logger.warning(message)
    elif level == "error":
        logger = getLogger(
            logName=logName, level=logging.ERROR, filePath=filePath, is_quiet=is_quiet)
        logger.error(message)
    elif level == "critical":
        logger = getLogger(
            logName=logName, level=logging.CRITICAL, filePath=filePath, is_quiet=is_quiet)
        logger.critical(message)
    else:
        logger = getLogger(
            logName=logName, level=logging.ERROR, filePath=filePath, is_quiet=is_quiet)
        logger.error(f"Unknown log level: {level}; using ERROR")
        logger.error(message)


# Initialize
main()

if __name__ == "__main__":
    print("Cabinet is a library not intended to be directly run. See README.md.")

if "cabinet" in sys.argv[0] and len(sys.argv) > 1:
    if sys.argv[-1] == 'config':
        setConfigItem('path_cabinet', input(
            f"Enter the full path of the directory where you want to store all data (currently {PATH_CABINET}):\n"))

    if sys.argv[1] == 'edit':
        if len(sys.argv) > 2:
            editFile(sys.argv[2])
        else:
            editFile(f"{PATH_CABINET}/settings.json")
