"""
Messages found throughout Cabinet
"""

NEW_SETUP_MSG_INTRO = """
Welcome to Cabinet!

How would you like to store your data?
1. MongoDB
2. Local Storage
"""

NEW_SETUP_MSG_CHECK_MONGODB = "Do you have a MongoDB instance set up? (y/n)\n"

NEW_SETUP_MSG_MONGODB_INSTRUCTIONS = """
Cabinet will use MongoDB to store and manage data.
Don't worry, this is easy and free for our purposes.

To create a MongoDB account using the free tier, follow these instructions:

1. Visit the MongoDB website: https://www.mongodb.com/
2. Click on the "Try Free" button.
3. Sign up for a free MongoDB account by providing the required information.
    - If prompted to create a new project, give any name you'd like.
4. Once you have created your account and logged in, create a new cluster.
    - Give the cluster any name you'd like.
5. Create a new database in your cluster with the name of your choice.
    - Name the collection "cabinet".
    - Unless you have a specific reason, don't add "additional preferences".

Press Enter once this is done.\n\n
"""

CONFIG_MONGODB_DB_NAME = """
Enter your MongoDB database name:\n
"""

CONFIG_MONGODB_CONNECTION_STRING = """
Enter your MongoDB connection string (URI).

Instructions: https://www.mongodb.com/docs/atlas/tutorial/connect-to-your-cluster/\n
"""

CONFIG_PATH_DIR_LOG = """
Enter the full path where you would like to store Cabinet logs.
(default: ~/.cabinet/log)\n
"""

CONFIG_EDITOR: str = """
Select your preferred editor from the list.
\n\n
If you're not sure, just hit Enter.
"""

EDIT_FILE_DEFAULT = """
Enter the path of the file you want to edit.
(default: edit Cabinet's MongoDB collection):\n
"""

ERROR_CONFIG_FILE_INVALID_MONGODB = """
Cabinet could not initialize properly.

Please check that all values in the configuration file are correct:
mongodb_enabled
editor
path_dir_log (optional)
mongodb_username
mongodb_password
mongodb_cluster_name
mongodb_db_name

Please check the values in ~./.config/cabinet/config.json and try again.

Otherwise, please leave feedback at https://github.com/tylerjwoodfin/cabinet/issues.\n\n
"""

ERROR_CONFIG_MISSING_VALUES = """
Cabinet could not initialize properly- some values appear to be missing.

Please check that all values in the configuration file exist and are properly set:
mongodb_enabled
editor
path_dir_log (optional)
mongodb_username (if mongodb_enabled is 'true')
mongodb_password (if mongodb_enabled is 'true')
mongodb_cluster_name (if mongodb_enabled is 'true')
mongodb_db_name (if mongodb_enabled is 'true')

Press Enter to open the file. Update any invalid values and try again.\n
"""

ERROR_CONFIG_JSON_DECODE = """
The configuration file is not valid JSON.

Do you want to replace it with an empty JSON file?
This will reset your MongoDB credentials, but your data will be safe.

(y/n)\n
"""

ERROR_LOCAL_STORAGE_JSON_DECODE = """
The local storage file is not valid JSON.

Do you want to replace it with an empty JSON file?
This will reset your data, but your configuration will be safe.

(y/n)\n
"""

ERROR_MONGODB_TIMEOUT = """
Timeout error: Could not connect to the MongoDB server:
"""

ERROR_MONGODB_DNS = """
DNS resolution failed for MongoDB server:
"""

ERROR_CONFIG_INVALID_EDITOR = """
I didn't understand that.

Your editor will be set to 'nano'.

Change this at any time with `cabinet --config`.
"""

ERROR_CONFIG_BROKEN_EDITOR = """
Cabinet's editor is set to %, but this editor cannot be used.

Please update the editor by using `cabinet --config` and updating
the editor attribute.

Your editor has been reset to 'nano', so if you try your last command
again, you shouldn't see this error.
"""

WARN_LOCAL_STORAGE_PATH = """
Cabinet's data file at ~/.cabinet/data.json is missing.

Creating a new one. Press Enter to continue (CTRL+C to exit).
"""
