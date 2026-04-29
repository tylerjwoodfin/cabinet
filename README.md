# Cabinet
Cabinet is a lightweight, flexible data organization tool that lets you manage your data with the simplicity of a JSON file or the power of MongoDB - your choice.

## Breaking changes in 3.0.0

This release changes how logging works when MongoDB is enabled. Plan upgrades accordingly.

- **`logdb()` removed.** Use `cab.log(...)` instead. There is no separate database-only logging API.
- **`--logdb` / `-ldb` removed.** Use `cabinet -l` / `--log` with `--level` as needed; the CLI follows the same rules as the Python API.
- **Default log collection is `log`.** When `mongodb_enabled` is true, `cab.log()` writes to the **`log`** collection in your configured `mongodb_db_name` (not a separate database and not the old default collection name `logs`). Override with `collection_name=` on `cab.log(...)` if you need a different collection.
- **`cab.log_query()` and `cabinet --query`:** When MongoDB is enabled, queries run against the same log collection (default `log`) and return lines in the same textual format as file-based logs. When MongoDB is disabled, behavior remains file-based under `path_dir_log`. Optional **`since`** uses the same semantics as **`cab.log_query_documents()`** (UTC cutoff or `timedelta` from now).
- **`cab.log_query_issues()`:** Returns **WARNING**, **ERROR**, and **CRITICAL** lines for the last 24 hours by default (MongoDB when enabled, otherwise today’s and yesterday’s files under `path_dir_log`; silently falls back to files if Mongo queries fail).
- **Structured log reads:** `cab.log_query_documents(level=..., since=..., limit=...)` returns recent log **documents** from MongoDB; `since` can be a `datetime` cutoff or a `timedelta` meaning “how far back from now.”
- **Naming:** Line-oriented search is **`cab.log_query(...)`**; raw documents use **`cab.log_query_documents(...)`**; **`cab.log_query_issues(...)`** is a convenience for “warning and above” in a time window.

Earlier releases:

- [Breaking change in 2.0.0](#breaking-change-in-200)

- [Cabinet](#cabinet)
  - [Breaking changes in 3.0.0](#breaking-changes-in-300)
  - [✨ Features](#-features)
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
    - [`append`](#append)
    - [`edit`](#edit)
    - [`edit_file`](#edit_file)
    - [`mail`](#mail-1)
    - [`log`](#log)
    - [`log_query`](#log_query)
    - [`log_query_issues`](#log_query_issues)
    - [`log_query_documents`](#log_query_documents)
  - [UI Module](#ui-module)
  - [Disclaimers](#disclaimers)
  - [Author](#author)


## ✨ Features

- Access your data across multiple projects
- Log messages to the MongoDB **`log`** collection when `mongodb_enabled` is true, or to daily files under `path_dir_log` when it is not (or when you pass `log_folder_path` to force file logging)
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
cabinet --configure
```

Requires **Python 3.10+** (see `python_requires` in `setup.cfg`).

### CLI Only
```bash
curl -s https://api.github.com/repos/tylerjwoodfin/cabinet/releases/latest \
| grep "browser_download_url" \
| cut -d '"' -f 4 \
| xargs curl -L -o cabinet.pex

sudo mv cabinet.pex /usr/local/bin/cabinet
```

## Dependencies

Outside of the standard Python library, the following packages are declared as dependencies (`setup.cfg` / package metadata):

- `pymongo`: MongoDB client and related errors.
- `prompt_toolkit`: Interactive CLI helpers (`cabinet.ui`).

For development, install optional test dependencies and run the suite:

```bash
pip install -e ".[dev]"
pytest
```

## Structure

- Data is stored in `~/.cabinet/data.json` or MongoDB
  - data from MongoDB is interacted with as if it were a JSON file
  - cache is written when retrieving data.
  - if cache is older than 1 hour, it is refreshed; otherwise, data is pulled from cache by default
- **Logs (file mode):** With MongoDB disabled, logs are written under `~/.cabinet/log/<YYYY-MM-DD>/LOG_DAILY_<date>.log` by default. Set `path_dir_log` in `~/.config/cabinet/config.json` to use another directory.
- **Logs (MongoDB mode):** With `mongodb_enabled` true, `cab.log()` writes a daily file under **`path_dir_log`** first, then best-effort to the **`log`** collection; MongoDB errors add a **WARNING** line to that same file plus a **stderr** warning, and do not block the primary file write. Use `log_folder_path` for **file-only** output, or `collection_name` to pick another collection. Stored Mongo timestamps are **UTC**; `cab.log_query()` formats line output in **local** time (`cabinet.log.format_log_timestamp_local`).

## CLI usage

Run `cabinet --help` for the authoritative list. Summary:

```
usage: cabinet [-h] [--configure] [--edit] [--edit-file EDIT_FILE]
               [--force-cache-update] [--no-create] [--get GET ...]
               [--put PUT ...] [--append APPEND ...] [--remove REMOVE ...]
               [--get-file GET_FILE] [--export] [--strip] [--log LOG]
               [--level LOG_LEVEL] [--tags LOG_TAGS] [--editor EDITOR]
               [--query [LOG_QUERY_FILE]] [--query-tags QUERY_TAGS]
               [--query-path QUERY_PATH] [--query-hostname QUERY_HOSTNAME]
               [--query-level QUERY_LEVEL] [--query-date QUERY_DATE]
               [--query-message QUERY_MESSAGE] [--mail]
               [--subject SUBJECT] [--body BODY] [--to TO_ADDR] [-v]

Options:
  -h, --help            show this help message and exit
  --configure, -config  Configure
  --edit, -e            Edit Cabinet's MongoDB as a JSON file
  --edit-file, -ef EDIT_FILE
                        Edit a specific file
  --force-cache-update  Disable using the cache for MongoDB queries
  --no-create           (for -ef) Do not create file if it does not exist
  --get, -g GET ...     Get a property from MongoDB
  --put, -p PUT ...     Put a property into MongoDB
  --append, -a APPEND ...
                        Append to a string or array (e.g. cabinet -a fruits banana)
  --remove, -rm REMOVE ...
                        Remove a property from MongoDB
  --get-file GET_FILE   Get file
  --export              Export MongoDB to ~/.cabinet/export
  --strip               (for --get-file) Surrounding whitespace is stripped by default; pass this flag to read file content without stripping
  --log, -l LOG         Log a message (file + best-effort MongoDB `log` collection when enabled, else file only)
  --level LOG_LEVEL     (for -l) Log level [debug, info, warn, error, critical]
  --tags LOG_TAGS       (for -l) Comma-separated tags for the log entry
  --editor EDITOR       (for --edit and --edit-file) Specify an editor
  --query, -q [LOG_QUERY_FILE]
                        Query log files (optional file name; defaults to today)
  --query-tags ...      (for --query) Comma-separated tags to filter by
  --query-path ...      (for --query) Filter by file path (fuzzy search)
  --query-hostname ...  (for --query) Filter by hostname
  --query-level ...     (for --query) Filter by log level [debug, info, warning, error, critical]
  --query-date ...      (for --query) Filter by date (YYYY-MM-DD)
  --query-message ...   (for --query) Search within message text
  -v, --version         Display the Cabinet version

Mail:
  --mail                Sends an email (requires --subject and --body)
  --subject, -s SUBJECT Email subject
  --body, -b BODY       Email body
  --to, -t TO_ADDR      To address(es)
```

When **`mongodb_enabled`** is true, `--query` reads from the **`log`** collection (same semantics as `Cabinet.log_query`; optional `collection_name=` only applies from Python).

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

  You can change this with `cabinet --configure` and modifying the `editor` attribute.

Your `config.json` should look something like this:
```json
{
    "path_dir_log": "/path/to/your/log/directory",
    "mongodb_db_name": "cabinet (or other name of your choice)",
    "editor": "nvim",
    "mongodb_enabled": true,
    "mongodb_connection_string": "<your connection string>"
}
```

### edit_file() shortcuts
- see example below to enable something like
  - `cabinet -ef shopping` from the terminal
    - rather than `cabinet -ef "~/path/to/shopping_list.md"`
  - or `cabinet.Cabinet().edit("shopping")`
    - rather than `cabinet.Cabinet().edit("~/path/to/whatever.md")`

Shortcut mapping example:

```json
{
  "path": {
    "edit": {
      "shopping": {
        "value": "~/path/to/whatever.md"
      },
      "todo": {
        "value": "~/path/to/whatever.md"
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

### `append`

Appends a value to an existing string (concatenation) or array. For other types (bool, int, float, etc.), prints a graceful error. Prints the updated value.

python:
```python
from cabinet import Cabinet

cab = Cabinet()

# Append to array: ['apple'] -> ['apple', 'banana']
cab.put("fruits", ["apple"])
cab.append("fruits", "banana", is_print=True)

# Append to string: 'apple' -> 'applebanana'
cab.put("fruits", "apple")
cab.append("fruits", "banana", is_print=True)
```

or terminal:
```bash
# Append to array: ['apple'] -> ['apple', 'banana']
cabinet -p fruits '["apple"]'
cabinet -a fruits banana

# Append to string: 'apple' -> 'applebanana'
cabinet -p fruits apple
cabinet -a fruits banana

# Nested paths
cabinet -a person tyler fruits banana
```

- **Arrays:** Adds the value as a new element. `['apple']` → `['apple', 'banana']`
- **Strings:** Concatenates. `'apple'` → `'applebanana'`
- **Other types:** Not allowed.
- **Missing key:** Not allowed.

### `edit`

terminal:
```bash

# opens file in the default editor (`cabinet --configure` -> 'editor'), saves upon exit
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

# After `path.edit.shopping.value` is set (e.g. `cabinet -p edit shopping value "~/path/to/shopping.md"`), this edits that file:

# opens file in the default editor (`cabinet --configure` -> 'editor'), saves upon exit
cab.edit("shopping")

# or you can edit a file directly...
cab.edit("/path/to/shopping.md")

# you can pass an 'editor' to override the default:
cab.edit("/path/to/shopping.md", editor="nvim")
```

terminal:
```bash
# assumes path -> edit -> shopping -> path/to/shopping.md has been set
cabinet -ef shopping

# or

cabinet -ef "/path/to/shopping.md"
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

With **`mongodb_enabled` true**, `cab.log()` writes a **daily file** under `path_dir_log` first, then inserts into the MongoDB **`log`** collection (or `collection_name=`). If MongoDB fails, the file entry still succeeds, a **WARNING** line describing the error is appended to that file, and stderr also prints a warning. With MongoDB off, or if you pass **`log_folder_path`**, only file logging runs (no Mongo insert).

python:
```python
from cabinet import Cabinet

cab = Cabinet()

# MongoDB mode (when mongodb_enabled is true): file under path_dir_log, then `log` collection
cab.log("Connection timed out")  # defaults to info if no level is set
cab.log("Debug breakpoint", level="debug", collection_name="debug_trace")  # optional collection override

# File mode (MongoDB disabled, or pass log_folder_path to force files while MongoDB is on)
# Files live under path_dir_log, e.g. ~/.cabinet/log/<YYYY-MM-DD>/LOG_DAILY_<date>.log

cab.log("This function hit a breakpoint", level="debug")
cab.log("Looks like the server is on fire", level="critical")
cab.log("This is fine", level="info")

# Log with tags (optional list of strings)
cab.log("Checked weather successfully", tags=["weather"])
cab.log("Starting Borg Backup...", tags=["backup", "start"])
cab.log("Pruning repository", tags=["backup", "prune"])
cab.log("Compacting repository", tags=["backup", "compact"])

# Custom daily log name / folder (file mode)
cab.log("30", log_name="LOG_TEMPERATURE")
cab.log("30", log_name="LOG_TEMPERATURE", log_folder_path="~/weather")

    # file format (without tags)
    # 2025-10-28 17:01:01,858 — INFO -> tools/weather.py:34@{hostname} -> Checking weather

    # file format (with tags)
    # 2025-09-27 02:01:09,012 — INFO [weather] -> tools/weather.py:116@cloud -> Checked weather successfully
```

terminal:
```bash
# Same routing as Python: file + MongoDB when enabled, else file only
cabinet -l "Connection timed out"
cabinet --log "Connection timed out"
cabinet --log "Server is on fire" --level "critical"

cabinet --log "Checked weather successfully" --tags "weather"
cabinet --log "Starting Borg Backup..." --tags "backup,start"
cabinet --log "Pruning repository" --level "info" --tags "backup,prune"
```

### `log_query`

Query logs by tags, path, hostname, level, date, and message. When **`mongodb_enabled`** is true, this queries the **`log`** collection (or pass `collection_name=`). Otherwise it searches rotating files under **`path_dir_log`**; optional **`log_file`** only applies in file mode. Optional **`since`** (`datetime` or `timedelta`, same as **`log_query_documents`**) restricts to entries on or after that UTC cutoff.

python:
```python
from datetime import timedelta
from cabinet import Cabinet

cab = Cabinet()

# Optional time window (file or MongoDB)
results = cab.log_query(since=timedelta(days=7), level="ERROR")

# MongoDB mode: filters apply to documents in the `log` collection
results = cab.log_query(tags=["weather"], level="INFO")

# MongoDB: optional collection override (defaults to `log`)
results = cab.log_query(tags=["audit"], collection_name="audit_logs")

# File mode: query today's file (log_file defaults to today's LOG_DAILY_*.log)
results = cab.log_query(tags=["weather"])

# File mode: query a specific file name
results = cab.log_query("LOG_DAILY_2025-09-27.log", tags=["weather"])

# Query by log level (in today's log)
results = cab.log_query(level="ERROR")

# Query by message content (case-insensitive fuzzy search)
results = cab.log_query(message="repository")

# Query by path (case-insensitive fuzzy search on file path after arrow)
results = cab.log_query(path="cabinet")

# Query by hostname
results = cab.log_query(hostname="cloud")

# Query by date (filters by timestamp in the log entry)
results = cab.log_query(date_filter="2025-09-27")

# Combine multiple filters on today's log
results = cab.log_query(
    tags=["backup"],
    level="INFO",
    message="repository"
)

# Combine multiple filters on specific log file
results = cab.log_query(
    "LOG_DAILY_2025-09-27.log",
    tags=["backup"],
    level="INFO",
    message="repository"
)
```

terminal:
```bash
# Query today's log (defaults to today if no log file specified)
cabinet --query --query-tags "weather"

# Short form
cabinet -q --query-tags "backup"

# Query by level
cabinet --query --query-level "ERROR"

# Query by message content
cabinet --query --query-message "repository"

# Query by path (fuzzy search)
cabinet --query --query-path "tools"

# Query by hostname
cabinet --query --query-hostname "cloud"

# Query by date
cabinet --query --query-date "2025-10-28"

# Combine multiple filters
cabinet --query --query-tags "backup" --query-level "INFO"

# Query specific log file
cabinet --query "LOG_DAILY_2025-09-27.log" --query-tags "weather"

# Complex query with multiple filters
cabinet -q "LOG_DAILY_2025-09-27.log" --query-tags "backup,weather" --query-level "INFO" --query-message "repository"
```

### `log_query_issues`

Returns formatted log lines at **WARNING**, **ERROR**, or **CRITICAL** within **`since`** (`timedelta` or UTC-aware `datetime`; **default: last 24 hours**). Uses the same storage as **`log_query`**: MongoDB when **`mongodb_enabled`** is true, otherwise scans today’s and yesterday’s daily files. If a Mongo query raises, results come from files without raising.

```python
from datetime import timedelta
from cabinet import Cabinet

cab = Cabinet()

for line in cab.log_query_issues():
    print(line)

# Custom window
lines = cab.log_query_issues(since=timedelta(days=2))
```

### `log_query_documents`

**MongoDB only** (raises `ValueError` if `mongodb_enabled` is false). Returns raw **documents** (newest first), with optional **`level`**, **`since`**, **`collection_name`**, and **`limit`**. Use **`since=timedelta(hours=24)`** for “last 24 hours,” or a timezone-aware **`datetime`** as an absolute cutoff.

python:
```python
from datetime import timedelta
from cabinet import Cabinet

cab = Cabinet()

rows = cab.log_query_documents(level="error", since=timedelta(days=7), limit=100)
for doc in rows:
    print(doc.get("timestamp"), doc.get("message"))
```

### `logdb`

Removed in **3.0.0** — see [Breaking changes in 3.0.0](#breaking-changes-in-300). Use **`cab.log(...)`** and **`cab.log_query*`** helpers instead.

## UI Module

The `cabinet.ui` submodule (`src/cabinet/ui.py`) provides interactive command-line components built on **prompt_toolkit**:

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
