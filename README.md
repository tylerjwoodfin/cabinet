# Cabinet
Cabinet is a lightweight, flexible data organization tool that lets you manage your data with the simplicity of a JSON file or the power of MongoDB - your choice.

- [Cabinet](#cabinet)
  - [✨ Features](#-features)
    - [Breaking change in 2.0.0](#breaking-change-in-200)
  - [Installation and Setup](#installation-and-setup)
    - [CLI and Python Library (Recommended)](#cli-and-python-library-recommended)
    - [CLI Only](#cli-only)
  - [Dependencies](#dependencies)
  - [Structure](#structure)
  - [CLI usage](#cli-usage)
  - [Configuration](#configuration)
    - [edit\_file() shortcuts](#edit_file-shortcuts)
    - [mail](#mail)
  - [Examples](#examples)
    - [`put`](#put)
    - [`get`](#get)
    - [`remove`](#remove)
    - [`edit`](#edit)
    - [`edit_file`](#edit_file)
    - [`mail`](#mail-1)
    - [`log`](#log)
    - [`logdb`](#logdb)
  - [UI Module](#ui-module)
  - [Disclaimers](#disclaimers)
  - [Author](#author)


## ✨ Features

- Access your data across multiple projects
- Log messages to MongoDB or a file of your choice
- Edit MongoDB as though it were a JSON file
- Send mail from the terminal
- Library for interactive command-line interface components using `prompt_toolkit`

### Breaking change in 2.0.0
- `mongodb_connection_string` replaces `mongodb_username` and `mongodb_password`.

## Installation and Setup

### CLI and Python Library (Recommended)

- Install [pipx](https://pypa.github.io/pipx/) if you don't have it already

- Install `cabinet`:
```bash
pipx install cabinet
cabinet --config
```

### CLI Only
```bash
curl -s https://api.github.com/repos/tylerjwoodfin/cabinet/releases/latest \
| grep "browser_download_url" \
| cut -d '"' -f 4 \
| xargs curl -L -o cabinet.pex

sudo mv cabinet.pex /usr/local/bin/cabinet
```

## Dependencies

Outside of the standard Python library, the following packages are included as part of `pipx install cabinet`:

- `pymongo`: Provides the MongoDB client and related errors.
- `prompt_toolkit`: Provides functionality for command-line interfaces.

## Structure

- Data is stored in `~/.cabinet/data.json` or MongoDB
  - data from MongoDB is interacted with as if it were a JSON file
  - cache is written when retrieving data.
  - if cache is older than 1 hour, it is refreshed; otherwise, data is pulled from cache by default
- Logs are written to `~/.cabinet/log/LOG_DAILY_YYYY-MM-DD` by default
  - You can change the path to something other than `~/.cabinet/log` as needed by setting/modifying `~/.config/cabinet/config.json` -> `path_dir_log`

## CLI usage
```markdown
Usage: cabinet [OPTIONS]

Options:
  -h, --help            show this help message and exit
  --configure, -config  Configure
  --edit, -e            Edit Cabinet as MongoDB as a JSON file
  --edit-file EDIT_FILE, -ef EDIT_FILE
                        Edit a specific file
  --force-cache-update  Disable using the cache for MongoDB queries
  --no-create           (for -ef) Do not create file if it does not exist
  --get GET [GET ...], -g GET [GET ...]
                        Get a property from MongoDB
  --put PUT [PUT ...], -p PUT [PUT ...]
                        Put a property into MongoDB
  --remove REMOVE [REMOVE ...], -rm REMOVE [REMOVE ...]
                        Remove a property from MongoDB
  --get-file GET_FILE   Get file
  --export              Exports MongoDB to ~/.cabinet/export
  --strip               (for --get-file) Whether to strip file content whitespace
  --log LOG, -l LOG     Log a message to the default location
  --level LOG_LEVEL     (for -l) Log level [debug, info, warn, error, critical]
  --editor EDITOR       (for --edit and --edit-file) Specify an editor to use
  -v, --version         Show version number and exit

Mail:
  --mail                Sends an email
  --subject SUBJECT, -s SUBJECT
                        Email subject
  --body BODY, -b BODY  Email body
  --to TO_ADDR, -t TO_ADDR
                        The "to" email address
```

## Configuration

- Configuration data is stored in `~/.config/cabinet/config.json`.

- Upon first launch, the tool will walk you through each option.
  - `path_dir_log` is the directory where logs will be stored by default.
  - `mongodb_enabled` is a boolean that determines whether MongoDB is used.
  - `mongodb_db_name` is the name of the database you want to use by default.
  - `mongodb_connection_string` is the connection string for MongoDB.
  - `editor` is the default editor that will be used when editing files.
  - You will be prompted to enter your MongoDB credentials (optional).
  - If you choose not to use MongoDB, data will be stored in `~/.cabinet/data.json`.

- Follow these instructions to find your MongoDB connection string: [MongoDB Atlas](https://docs.atlas.mongodb.com/tutorial/connect-to-your-cluster/) or [MongoDB](https://docs.mongodb.com/manual/reference/connection-string/) (for local MongoDB, untested).

- You will be asked to configure your default editor from the list of available editors on
  your system. If this step is skipped, or an error occurs, `nano` will be used.

  You can change this with `cabinet --config` and modifying the `editor` attribute.

Your `config.json` should look something like this:
```json
{
    "path_dir_log": "/path/to/your/log/directory",
    "mongodb_db_name": "cabinet (or other name of your choice)",
    "editor": "nvim",
    "mongodb_enabled": true,
    "mongodb_connection_string": "<your connection string>",
}
```

### edit_file() shortcuts
- see example below to enable something like
  - `cabinet -ef shopping` from the terminal
    - rather than `cabinet -ef "~/path/to/shopping_list.md"`
  - or `cabinet.Cabinet().edit("shopping")`
    - rather than `cabinet.Cabinet().edit("~/path/to/whatever.md")`

file:
```json
# example only; these commands will be unique to your setup

{
  "path": {
    "edit": {
      "shopping": {
        "value": "~/path/to/whatever.md",
      },
      "todo": {
        "value": "~/path/to/whatever.md",
      }
    }
  }
}
```

set from terminal:
```bash
cabinet -p edit shopping value "~/path/to/whatever.md"
cabinet -p edit todo value "~/path/to/whatever.md"
```

### mail

- It is NEVER a good idea to store your password openly either locally or in MongoDB; for this reason, I recommend a "throwaway" account that is only used for sending emails, such as a custom domain email.
- Gmail and most other mainstream email providers won't work with this; for support, search for sending mail from your email provider with `smtplib`.
- In Cabinet (`cabinet -e`), add the `email` object to make your settings file look like this example:

file:
```json
{
    "email": {
        "from": "throwaway@example.com",
        "from_pw": "example",
        "from_name": "Cabinet (or other name of your choice)",
        "to": "destination@protonmail.com",
        "smtp_server": "example.com",
        "imap_server": "example.com",
        "port": 123
    }
}
```

set from terminal:
```bash
cabinet -p email from throwaway@example.com
cabinet -p email from_pw example
...
```

## Examples

### `put`

python:
```python
from cabinet import Cabinet

cab = Cabinet()

cab.put("employee", "Tyler", "salary", 7.25)
```

or terminal:
```bash
cabinet -p employee Tyler salary 7.25
```

results in this structure in MongoDB:
```json
{
    "employee": {
        "Tyler": {
            "salary": 7.25 # or "7.25" if done from terminal
        }
    }
}
```

### `get`

python:
```python
from cabinet import Cabinet

cab = Cabinet()

print(cab.get("employee", "Tyler", "salary"))

# or cab.get("employee", "Tyler", "salary", is_print = True)
```

or terminal:
```bash
cabinet -g employee Tyler salary
```
- optional: `--force-cache-update` to force a cache update

results in:
```bash
7.25
```

### `remove`

python:
```python
from cabinet import Cabinet

cab = Cabinet()

cab.remove("employee", "Tyler", "salary")
```

or terminal:
```bash
cabinet -rm employee Tyler salary
```

results in this structure in MongoDB:
```json
{
    "employee": {
        "tyler": {}
    }
}
```

### `edit`

terminal:
```bash

# opens file in the default editor (`cabinet --config` -> 'editor'), saves upon exit
cabinet -e

# or

cabinet --edit

# you can add an 'editor':

cabinet -e --editor=code
```

### `edit_file`

python:
```python
from cabinet import Cabinet

cab = Cabinet()

# if put("path", "edit", "shopping", "/path/to/shopping.md") has been called, this will edit the file assigned to that shortcut.

# opens file in the default editor (`cabinet --config` -> 'editor'), saves upon exit
cab.edit("shopping")

# or you can edit a file directly...
cab.edit("/path/to/shopping.md")

# you can pass an 'editor' to override the default:
cab.edit("/path/to/shopping.md", editor="nvim")
```

terminal:
```bash
# assumes path -> edit -> shopping -> path/to/shopping.md has been set
cabinet -ef shoppping

# or

cabinet -ef "/path/to/shopping.md"

# or
```

### `mail`

python:
```python

from cabinet import Mail

mail = Mail()

mail.send('Test Subject', 'Test Body')
```

terminal:
```bash
cabinet --mail --subject "Test Subject" --body "Test Body"

# or

cabinet --mail -s "Test Subject" -b "Test Body"
```

### `log`

python:
```python
from cabinet import Cabinet

cab = Cabinet()

# writes to a file named LOG_DAILY_YYYY-MM-DD in `~/.cabinet/log` inside a YYYY-MM-DD folder
# writes somewhere other than `~/.cabinet/log`, if `~/.config/cabinet/config.json` has `path_dir_log` set

cab.log("Connection timed out") # defaults to 'info' if no level is set
cab.log("This function hit a breakpoint", level="debug")
cab.log("Looks like the server is on fire", level="critical")
cab.log("This is fine", level="info")

# writes to a file named LOG_TEMPERATURE in the default log directory
cab.log("30", log_name="LOG_TEMPERATURE")

# writes to a file named LOG_TEMPERATURE in ~/weather
cab.log("30", log_name="LOG_TEMPERATURE", log_folder_path="~/weather")

    # format
    # 2021-12-29 19:29:27,896 — INFO — 30

```

terminal:
```bash
# defaults to 'info' if no level is set
cabinet -l "Connection timed out"

# -l and --log are interchangeable
cabinet --log "Connection timed out"

# change levels with --level
cabinet --log "Server is on fire" --level "critical"
```

### `logdb`

python:
```python
from cabinet import Cabinet
cab = Cabinet()
cab.logdb("Connection timed out") # logs default to a `logs` collection in MongoDB
cab.logdb("This function hit a breakpoint", level="debug", collection_name="debugging logs") # customize the collection name
cab.logdb("Temperature changed significantly", level="critical", db_name="weather") # customize the database name
cab.logdb("This is fine", level="info", cluster_name="myCluster") # customize the cluster name
```
terminal:
```bash
# defaults to 'info' if no level is set
cabinet -ldb "Connection timed out"
# -l and --log are interchangeable
cabinet --logdb "Connection timed out"
# change levels with --level
cabinet --logdb "Server is on fire" --level "critical"
```

## UI Module

The `cabinet.ui` module provides interactive command-line interface components:

```python
from cabinet.ui import list_selection, render_html, confirmation

# List selection
items = ["Option 1", "Option 2", "Option 3"]
selected_index = list_selection(items, "Choose an option:")

# HTML rendering
render_html("<b>Bold text</b> and <i>italic text</i>")

# Confirmation dialog
result = confirmation("Do you want to proceed?", "Confirmation")
```

## Disclaimers

- Although I've done quite a bit of testing, I can't guarantee everything that works on my machine will work on yours. Always back up your data to multiple places to avoid data loss.
- If you find any issues, please contact me... or get your hands dirty and raise a PR!

## Author

- Tyler Woodfin
  - [GitHub](https://www.github.com/tylerjwoodfin)
  - [LinkedIn](https://www.linkedin.com/in/tylerjwoodfin)
  - [Website](http://tyler.cloud)
