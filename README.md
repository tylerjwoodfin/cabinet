# Cabinet

Cabinet is a lightweight, flexible data organization tool that lets you manage your data with the simplicity of a JSON file or the power of MongoDB - your choice.

## Breaking changes in 3.0.0

This release changes how logging works. Plan upgrades accordingly.

- `**logdb()` removed.** Use `cab.log(...)` instead. There is no separate database-only logging API.
- `**--logdb` / `-ldb` removed.** Use `cabinet -l` / `--log` with `--level` as needed; the CLI follows the same rules as the Python API.
- **File-first logging:** `cab.log()` / `cabinet --log` **always** write to **local-only** daily files under `path_dir_log` on each machine. Logging does **not** use MongoDB. Optional `**logging.loki_enabled`** appends one structured JSON line per event to a sibling `***.jsonl**` file so **Promtail on that same machine** can ship to a **central Loki** (see [Logging and Loki (optional)](#logging-and-loki-optional)).
- `**cab.log_query()` and `cabinet --query`:** Search **log files** under `path_dir_log` only. MongoDB is for Cabinet’s **configuration/data** collection, not logs. Optional `**since`** filters by UTC cutoff or `timedelta` (compared using each line’s local timestamp).
- `**cab.log_query_issues()`:** Returns **WARNING**, **ERROR**, and **CRITICAL** lines for the last 24 hours by default by scanning today’s and yesterday’s daily files under `path_dir_log`.
- `**cab.log_query_documents()` removed:** Use **Loki/Grafana** for centralized structured log views, or read `**.jsonl`** / `**.log**` files directly.

- [Breaking change in 2.0.0](#breaking-change-in-200)
- [Cabinet](#cabinet)
  - [Breaking changes in 3.0.0](#breaking-changes-in-300)
  - [✨ Features](#-features)
  - [Minimal Installation and Setup](#installation-and-setup)
    - [CLI and Python Library (Recommended)](#cli-and-python-library-recommended)
    - [CLI Only](#cli-only)
  - [Dependencies](#dependencies)
  - [Structure](#structure)
  - [CLI usage](#cli-usage)
  - [Configuration](#configuration)
    - [Logging and Loki (optional)](#logging-and-loki-optional)
    - [editfile() shortcuts](#edit_file-shortcuts)
    - [mail](#mail)
  - [Examples](#examples)
    - `[put](#put)`
    - `[get](#get)`
    - `[remove](#remove)`
    - `[append](#append)`
    - `[edit](#edit)`
    - `[edit_file](#edit_file)`
    - `[mail](#mail-1)`
    - `[log](#log)`
    - `[log_query](#log_query)`
    - `[log_query_issues](#log_query_issues)`
    - [Loki queries](#log_query_loki-log_query_documents_loki-log_query_issues_loki)
  - [UI Module](#ui-module)
  - [Disclaimers](#disclaimers)
  - [Author](#author)

## ✨ Features

- Access your data across multiple projects
- Log messages to **local** files under `path_dir_log` (and optional **local `*.jsonl`** for that host’s Promtail). `**cab.log_query()**` / `**cab.log_query_issues()**` read **files**; `**cab.log_query*_loki()`** reads **Loki** when `**logging.loki_url`** is set. MongoDB is only for **Cabinet data**, not logs.
- Edit MongoDB as though it were a JSON file (Cabinet **data** only, not logs)
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
- **Logs:** `**cab.log()`** / `**cabinet --log**` append to `**path_dir_log/<YYYY-MM-DD>/**` on **that machine only**. Optional **JSONL** for `**logging.loki_enabled`** (scraped by **Promtail on the same host**). `**cab.log_query()`** / `**cab.log_query_issues()**` scan local `**.log**` files. `**cab.log_query_loki()**` / `**cab.log_query_documents_loki()**` / `**cab.log_query_issues_loki()**` query **Loki** via `**logging.loki_url`**. MongoDB stores Cabinet **variables** only, not logs.

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
  --log, -l LOG         Log a message (local files; optional JSONL when logging.loki_enabled)
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

`--query` searches **log files** under `path_dir_log`, the same as Python `**Cabinet.log_query`**.

## Configuration

- Configuration data is stored in `~/.config/cabinet/config.json`.
- Upon first launch, the tool will walk you through each option.
  - `path_dir_log` is the **local** directory where logs are stored on **this machine** by default. If this is a multi-machine setup, **do not** put this under Syncthing, NFS, or other shared folders (see [Logging and Loki](#logging-and-loki-optional)). A practical default is **`~/.local/share/cabinet/log`**, which stays off most Syncthing profiles even if you sync `~/.cabinet`.
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
    "path_dir_log": "/home/you/.local/share/cabinet/log",
    "mongodb_db_name": "cabinet (or other name of your choice)",
    "editor": "nvim",
    "mongodb_enabled": true,
    "mongodb_connection_string": "<your connection string>",
    "logging": {
        "loki_enabled": true,
        "log_dir": "/home/you/.local/share/cabinet/log",
        "loki_url": "http://loki.example.com:3100"
    }
}
```

Use a directory that exists only on **this** machine. If you previously used something like `~/syncthing/...` for logs, move `path_dir_log` (and `logging.log_dir` if set) to a non-synced path such as **`~/.local/share/cabinet/log`** or **`~/.cache/cabinet/log`**.

The `**logging**` object is optional. `loki_enabled` turns on parallel **JSON Lines** files (`*.jsonl`) next to each `*.log` on **that machine’s local disk** for local Promtail to scrape. `**loki_url`** enables `**cab.log_query*_loki(...)**` helpers against a Loki server (central or tunneled). `**log_dir**`, when set, overrides the on-disk log directory for `cab.log()` (if omitted, top-level `**path_dir_log**` is used).

### Logging and Loki (optional)

**Architecture (multi-machine):**

```text
log() → local *.log + *.jsonl (this host only) → Promtail (this host) → Loki (one central server) → Grafana
```

- **File-first:** Every `cab.log()` / `cabinet -l` line goes to the classic `**.log`** format on **local disk**.
- **Do not share log directories:** Set `path_dir_log` / `logging.log_dir` to a **local-only** directory on each machine. **Do not** use Syncthing, NFS, or other shared folders for Cabinet logs: multiple writers to the same files cause sync conflicts, torn lines, duplicate or missing ingestion, and undefined ordering. That pattern is unsupported.
  - **Syncthing:** Even if Cabinet’s config lives under a synced tree, point **`path_dir_log`** at something **outside** your Syncthing folders (for example **`~/.local/share/cabinet/log`** or **`~/.cache/cabinet/log`**). **`mkdir -p ~/.local/share/cabinet/log`** on each host before logging.
- **No log push HTTP:** `cab.log()` never POSTs to Loki; **Promtail on each machine** tails local `*.jsonl` and pushes to Loki. **Reads** from Loki (`cab.log_query*_loki`) use HTTP only when **`logging.loki_url`** is set.
- **Optional JSONL:** With `logging.loki_enabled`, each event also appends one JSON object per line to `**LOG_DAILY_<date>.jsonl`** in the same date folder (fields include `timestamp`, `level`, `message`, `tags`, `source`, `hostname` from `socket.gethostname()` on that host).
- **Install Loki, Grafana, and Promtail (this repo’s Docker stack):** You need **[Docker](https://docs.docker.com/engine/install/)** and the **[Docker Compose plugin](https://docs.docker.com/compose/install/)** on any machine that will run containers. Upstream docs: **[Grafana Loki](https://grafana.com/docs/loki/latest/)**, **[Promtail](https://grafana.com/docs/loki/latest/send-data/promtail/)**, source **[github.com/grafana/loki](https://github.com/grafana/loki)**.
  - **Central server (Loki + Grafana):** One host runs the stack so all Promtail agents can push to it.
    ```bash
    cd /path/to/your/checkout/docker/loki
    cp .env.example .env    # optional: set GRAFANA_PORT
    docker compose up -d
    ```
    This starts **Loki** (port **3100** by default) and **Grafana** (host port from `.env`; login **admin** / **admin**). It does **not** start Promtail.
  - **Each Cabinet host (Promtail only):** In the same **`docker/loki`** directory, copy **`promtail.env.example`** → **`promtail.env`**, set **`LOKI_URL`** (reachable from that host) and **`CABINET_LOG_DIR`** (same absolute path as **`path_dir_log`** / **`logging.log_dir`** in that machine’s Cabinet config), then:
    ```bash
    cd /path/to/your/checkout/docker/loki
    docker compose -f docker-compose.promtail.yml up -d
    ```
    More detail, including **`host.docker.internal`** vs LAN IP for **`LOKI_URL`**, is in **[`../docker/loki/README.md`](../docker/loki/README.md)** (sibling of this **`cabinet`** repo when both live under the same parent directory).
- **Multi-machine example:** Host **cloud** runs Cabinet → local JSONL → Promtail → Loki; host **rainbow** same; host **ice** same. In Grafana Explore, filter by source host with LogQL labels such as `{job="cabinet", hostname="rainbow"}` (hostname comes from the JSON line).
- **Turn off Loki shipping:** Set `loki_enabled` to `false`, or stop Promtail on that host. Cabinet does not require Docker.
- **Explore logs in Grafana:** **Explore** → datasource **Loki** → e.g. `{job="cabinet"}` or `{job="cabinet", hostname="cloud"}`.
- **Query from Python (Loki):** Set `**logging.loki_url`** to your **reachable** Loki base URL (e.g. `http://central:3100` or via VPN). Use `**cab.log_query_loki(...)`**, `**cab.log_query_documents_loki(...)**`, `**cab.log_query_issues_loki(...)**`. Optional `**logging.loki_job**` (default `cabinet`, must match Promtail’s `job` label) and `**logging.loki_query_timeout**` (seconds, default `30`).
- **Config example (logging + Loki reads):**
  ```json
  "logging": {
      "loki_enabled": true,
      "log_dir": "/home/you/.local/share/cabinet/log",
      "loki_url": "http://loki.example.com:3100",
      "loki_job": "cabinet",
      "loki_query_timeout": 30
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

`**cab.log()**` / `**cabinet --log**` write only to **local files** (classic `**.log`** lines). There are **no** network calls. If `**logging.loki_enabled`** is true in `config.json`, each event also appends a structured line to a matching **local `.jsonl`** file for **Promtail on that host** to ship to **central Loki**. Failures to write are printed to **stderr** and do not propagate as exceptions from `log()`.

**MongoDB** is only for Cabinet’s `**get` / `put`** data. Logs are **files** (and optional **Loki**).

```python
from cabinet import Cabinet

cab = Cabinet()

# Always: daily file under path_dir_log, e.g. ~/.cabinet/log/<YYYY-MM-DD>/LOG_DAILY_<date>.log
# If logging.loki_enabled: also ~/.cabinet/log/<YYYY-MM-DD>/LOG_DAILY_<date>.jsonl
cab.log("Connection timed out")  # defaults to info if no level is set
cab.log("Debug breakpoint", level="debug")

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
# Same file routing as Python (optional JSONL if logging.loki_enabled in config)
cabinet -l "Connection timed out"
cabinet --log "Connection timed out"
cabinet --log "Server is on fire" --level "critical"

cabinet --log "Checked weather successfully" --tags "weather"
cabinet --log "Starting Borg Backup..." --tags "backup,start"
cabinet --log "Pruning repository" --level "info" --tags "backup,prune"
```

### `log_query`

Query **log files** under `**path_dir_log`** by tags, path, hostname, level, date, and message. Optional `**since**` (`datetime` or `timedelta`) restricts to entries on or after that UTC cutoff (using each line’s parsed local time).

```python
from datetime import timedelta
from cabinet import Cabinet

cab = Cabinet()

# Optional time window
results = cab.log_query(since=timedelta(days=7), level="ERROR")

results = cab.log_query(tags=["weather"], level="INFO")

# Query today's file (log_file defaults to today's LOG_DAILY_*.log)
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

Returns formatted log lines at **WARNING**, **ERROR**, or **CRITICAL** within **since** (`timedelta` or UTC-aware `datetime`; **default: last 24 hours**). Scans **today’s** and **yesterday’s** daily `**.log`** files under `**path_dir_log**` (same line format as `**log_query**`).

```python
from datetime import timedelta
from cabinet import Cabinet

cab = Cabinet()

for line in cab.log_query_issues():
    print(line)

# Custom window
lines = cab.log_query_issues(since=timedelta(days=2))
```

### `log_query_loki`, `log_query_documents_loki`, `log_query_issues_loki`

Loki-backed queries (HTTP to `**logging.loki_url**`). Same filter ideas as `**log_query**` and `**log_query_issues**`: **since** / **end**, **level**, **hostname**, **tags**, **path** (source file substring), **message**, **date_filter**, **log_file** (matches Promtail’s `**filename`** label when present), **limit**. Returns formatted lines or `**dict`** rows with `**timestamp**` as `**datetime**` (UTC) plus `**_loki**` metadata.

```python
from datetime import timedelta
from cabinet import Cabinet

cab = Cabinet()

lines = cab.log_query_loki(level="error", since=timedelta(days=7), limit=100)
rows = cab.log_query_documents_loki(since=timedelta(hours=24), limit=50)
issues = cab.log_query_issues_loki(since=timedelta(hours=24))
```

### `logdb`

Removed in **3.0.0** — see [Breaking changes in 3.0.0](#breaking-changes-in-300). Use `**cab.log(...)`**, `**cab.log_query()**` / `**cab.log_query_issues()**`, and the `**cab.log_query*_loki()**` helpers instead.

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

