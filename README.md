# cabinet
A Python library to easily manage data with MongoDB and across other files.

Supports a cli, email, and event logging.

## MongoDB Update! - 2023-06-25
- In this latest release, the tool has been redesigned from the ground up to use MongoDB.
- MongoDB elevates Cabinet to the best of both worlds: a secure database with the ability to edit 
  as if it were a JSON structure.
- Every function has been tested for compatibility with earlier releases, but it's likely
  there will be some edge case bugs to iron out. I use this tool extremely often in my day-to-day
  use, so these should be patched quickly, once discovered. Please report issues as you find them.

## Features

- Read and write data in MongoDB and/or the JSON files of your choice
- Provides easy shortcuts to MongoDB actions
- Log to a file/directory of your choice without having to configure `logger` each time
- Send/receive mail using `cabinet.Cabinet().mail()`

## Dependencies

- Python >= 3.6
- MongoDB
- Pymongo (`pip install pymongo`)
- smtplib

## Structure

- Data is stored in MongoDB; simply plug in your credentials.
  - cache is written when retrieving data.
  - if cache is older than 1 hour, it is refreshed; otherwise, data is pulled from cache by default
- Logs are written to `~/.cabinet/log/LOG_DAILY_YYYY-MM-DD` by default
  - this can be changed as needed (per log or otherwise)

## Installation and Setup

```bash
  python3 -m pip install cabinet
  python3 -m pip install pymongo
  cabinet --config
```

## CLI usage
```
Usage: cabinet [OPTIONS]

Options:
  -h, --help              Show this help message and exit
  --configure, -config    Configure
  --export                Export the data in MongoDB to a JSON file
  --edit, -e              Edit MongoDB in the default editor as a JSON file
  --edit-file, -ef        Edit a specific file
  --no-create             (for -ef) Do not create file if it does not exist
  --get, -g               Get a property from MongoDB (nesting supported)
  --put, -p               Put a property into MongoDB (nesting supported)
  --remove, -rm           Removes a property from MongoDB
  --get-file              Returns the file specified
  --strip                 (for --get-file) Whether to strip file content whitespace
  --log, -l               Log a message to the default location
  --level                 (for -l) Log level [debug, info, warn, error, critical]
  -v, --version           show version number and exit

Mail:
  --mail                Sends an email
  --subject SUBJECT, -s SUBJECT
                        Email subject
  --body BODY, -b BODY  Email body
  --to TO_ADDR, -t TO_ADDR
```

## Configuration

- Upon first launch, the tool will prompt you to enter your MongoDB credentials, as well as
  the cluster name and Database name. These are stored only within the package, as a file named
  `cabinet_config.json`.

### edit_file() shortcuts
- see example below to enable something like
  - `cabinet -ef shopping` from the terminal
    - rather than `cabinet -ef "/home/{username}/path/to/shopping_list.md"`
  - or `cabinet.Cabinet().edit("shopping")`
    - rather than `cabinet.Cabinet().edit("/home/{username}/path/to/whatever.md")`

file:
```
# example only; these commands will be unique to your setup

{
  "path": {
    "edit": {
      "shopping": {
        "value": "/home/{username}/path/to/whatever.md",
      },
      "todo": {
        "value": "/home/{username}/path/to/whatever.md",
      }
    }
  }
}
```

set from terminal:
```
cabinet -p edit shopping value "/home/{username}/path/to/whatever.md"
cabinet -p edit todo value "/home/{username}/path/to/whatever.md"
```

### mail

- It is NEVER a good idea to store your password in plaintext; for this reason, I strongly recommend a "throwaway" account that is only used for sending emails
- Gmail (as of May 2022) and most other mainstream email providers won't work with this; for support, search for sending mail from your email provider with `smtplib`.
- In MongoDB, add the `email` object to make your settings file look like this example:

file:
```
{
    "email": {
        "from": "throwaway@example.com",
        "from_pw": "example",
        "from_name": "Cabinet",
        "to": "destination@protonmail.com",
        "smtp_server": "example.com",
        "imap_server": "example.com",
        "port": 123
    }
}
```

set from terminal:
```
cabinet -p email from throwaway@example.com
cabinet -p email from_pw example
...
```

## Examples

### `put`

python:
```
from cabinet import Cabinet

cab = Cabinet()

cab.put("employee", "Tyler", "salary", 7.25)
```

or terminal:
```
cabinet -p employee Tyler salary 7.25
```

results in this structure in MongoDB:
```
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
```
from cabinet import Cabinet

cab = Cabinet()

print(cab.get("employee", "Tyler", "salary"))

# or cab.get("employee", "Tyler", "salary", is_print = True)
```

or terminal:
```
cabinet -g employee Tyler salary
```
- optional: `--no-cache` to force cache refresh

results in:
```
7.25
```

### `remove`

python:
```
from cabinet import Cabinet

cab = Cabinet()

cab.remove("employee", "Tyler", "salary")
```

or terminal:
```
cabinet -rm employee Tyler salary
```

results in this structure in MongoDB:
```
{
    "employee": {
        "tyler": {}
    }
}
```

### `edit_file`

python:
```
from cabinet import Cabinet

cab = Cabinet()

# if put("path", "edit", "shopping", "/path/to/shopping.md") has been called, this will edit the file assigned to that shortcut.

# opens file in Vim, saves upon exit
cab.edit("shopping")

# or you can edit a file directly...
cab.edit("/path/to/shopping.md")
```

terminal:
```
# assumes path -> edit -> shopping -> path/to/shopping.md has been set
cabinet -ef shoppping

or 

cabinet -ef "/path/to/shopping.md"
```

### `mail`

python:
```

from cabinet import Mail

mail = Mail()

mail.send('Test Subject', 'Test Body')

```

terminal:
```
cabinet --mail --subject "Test Subject" --body "Test Body"

# or

cabinet --mail -s "Test Subject" -b "Test Body"
```

### `log`

python:
```
from cabinet import Cabinet

cab = Cabinet()

# writes to a file named LOG_DAILY_YYYY-MM-DD in the default log folder (or cab.get('path', 'log')) inside a YYYY-MM-DD folder
cab.log("Connection timed out") # defaults to 'info' if no level is set
cab.log("This function hit a breakpoint", level="debug")
cab.log("Looks like the server is on fire", level="critical")
cab.log("This is fine", level="info")

# writes to a file named LOG_TEMPERATURE
cab.log("30", log_name="LOG_TEMPERATURE")

# writes to a file named LOG_TEMPERATURE in /home/{username}/weather
cab.log("30", log_name="LOG_TEMPERATURE", log_folder_path="/home/{username}/weather")

    # format
    # 2021-12-29 19:29:27,896 — INFO — 30

```

terminal:
```
# defaults to 'info' if no level is set
cab -l "Connection timed out" 

# -l and --log are interchangeable
cab --log "Connection timed out"

# change levels with --level
cab --log "Server is on fire" --level "critical"
```

## Disclaimers

- Although I've done quite a bit of testing, I can't guarantee everything that works on my machine will work on yours. Always back up your data to multiple places to avoid data loss.
- If you find any issues, please contact me... or get your hands dirty and raise a PR!

## Unit Tests
- Unit tests are available in `test/`; use `pytest test/` to run them.

## Author

- Tyler Woodfin
  - [GitHub](https://www.github.com/tylerjwoodfin)
  - [Website](http://tyler.cloud)
