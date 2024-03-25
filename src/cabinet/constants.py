"""
Messages found throughout Cabinet
"""

import pathlib

NEW_SETUP_MSG_INTRO = (
    "Welcome to Cabinet!\n\n"
    "Do you have a MongoDB instance set up? (y/n)\n"
)

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

CONFIG_MONGODB_USERNAME = """
Enter your MongoDB username (not your email address):\n
"""

CONFIG_MONGODB_PASSWORD = """
Enter your MongoDB password:\n
"""

CONFIG_MONGODB_CLUSTER_NAME = """
Enter your MongoDB cluster name:\n
"""

CONFIG_MONGODB_DB_NAME = """
Enter your MongoDB database name:\n
"""

CONFIG_PATH_CABINET = f"""
Enter the full path where you would like to store Cabinet data,
such as logs and settings.

\n
Default: {pathlib.Path.home().resolve()}/.cabinet
"""

EDIT_FILE_DEFAULT = """
Enter the path of the file you want to edit.
(default: edit Cabinet's MongoDB collection):\n
"""

ERROR_CONFIG_FILE_INVALID = """
Cabinet could not initialize properly.

Please check that all values in the configuration file are correct:
mongodb_username
mongodb_password
mongodb_cluster_name
mongodb_db_name
path_cabinet

Please try re-running Cabinet.

Otherwise, please leave feedback at https://github.com/tylerjwoodfin/cabinet/issues.\n\n
"""

ERROR_CONFIG_MISSING_VALUES = """
Cabinet could not initialize properly.

Please check that all values in the configuration file are correct:
mongodb_username
mongodb_password
mongodb_cluster_name
mongodb_db_name
path_cabinet

Press Enter to open the file. Update any invalid values and try again.\n
"""

ERROR_CONFIG_JSON_DECODE = """
The configuration file is not valid JSON.

Do you want to replace it with an empty JSON file?
This will reset your MongoDB credentials, but your data will be safe.

(y/n)\n
"""

ERROR_MONGODB_TIMEOUT = """
Timeout error: Could not connect to the MongoDB server:
"""

ERROR_MONGODB_DNS = """
DNS resolution failed for MongoDB server:
"""