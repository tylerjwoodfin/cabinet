# cabinet
A Python library to easily read and write settings in JSON files across repos. Supports email and event logging.

## Features

- Read and write data in the JSON files of your choice
- Log to a file/directory of your choice without having to configure `logger` each time
- Send/receive mail using `cabinet.mail`

## Structure

- Data is stored in a `settings.json` file in the location of your choice
- Logs are written to `/path/to/cabinet/log` by default

## Installation and Setup

```bash
  python3 -m pip install cabinet

  cabinet config
```

## Configuration

- To choose where `settings.json` is stored, use `cabinet config` and follow the prompts.

- To choose where logs will be stored, edit `settings.json` and set `path -> log` to the full path to the log folder. (in other words, `{"path": "log": "/path/to/folder"}`)

### edit
- see example below to enable something like `cabinet edit shopping` from the terminal
  - or `cabinet.edit("shopping")`, rather than `cabinet.edit("/home/{username}/path/to/shopping.md")`

```
# example only; these commands will be unique to your setup

{
  "path": {
    "edit": {
      "shopping": {
        "value": "/home/{username}/path/to/shopping.md",
      },
      "todo": {
        "value": "/home/{username}/path/to/todo.md",
      }
    }
  }
}
```

### mail

- It is NEVER a good idea to store your password in plaintext; for this reason, I strongly recommend a "throwaway" account that is only used for sending emails
- Gmail (as of May 2022) and most other mainstream email providers won't work with this; for support, search for sending mail from your email provider with `smtplib`.
- In `settings.json`, add the `email` object to make your settings file look like this example:

```
{
    "email": {
        "from": "throwaway@example.com",
        "from_pw": "example",
        "from_name": "Raspberry Pi",
        "to": "destination@protonmail.com",
        "smtp_server": "example.com",
        "imap_server": "example.com",
        "port": 123
    }
}
```

## Examples

### `set`

```
from cabinet import cabinet

cabinet.set("employee", "Tyler", "salary", 7.25)
```

results in this structure in settings.json:

```
{
    "employee": {
        "Tyler": {
            "salary": 7.25
        }
    }
}
```

### `get`

```
from cabinet import cabinet

print(cabinet.get("employee", "Tyler", "salary")) # given example settings.json above
```

```
> python3 test.py
> 7.25
```

### `edit`

```
from cabinet import cabinet

# if set("path", "edit", "shopping", "/path/to/shopping.md") has been called, this will edit the file
# assigned to that shortcut.

# opens file in Vim, saves upon exit
cabinet.edit("shopping")

# or you can edit a file directly...
cabinet.edit("/path/to/shopping.md")
```

### `mail`

```

from cabinet import mail

mail.send('Test Subject', 'Test Body')

```

### `log`

```

from cabinet import cabinet

# writes to a file named LOG_DAILY YYYY-MM-DD in the default log folder (or cabinet.get('path', 'log')) inside a YYYY-MM-DD folder

cabinet.log("Connection timed out") # defaults to 'info' if no level is set
cabinet.log("This function hit a breakpoint", level="debug")
cabinet.log("Looks like the server is on fire", level="critical")
cabinet.log("This is fine", level="info")

# writes to a file named LOG_TEMPERATURE

cabinet.log("30", logName="LOG_TEMPERATURE")

# writes to a file named LOG_TEMPERATURE in /home/{username}/weather

cabinet.log("30", logName="LOG_TEMPERATURE", filePath="/home/{username}/weather")

    # format
    # 2021-12-29 19:29:27,896 — INFO — 30

```

## Dependencies

- Python >= 3.6
- smtplib

## Disclaimers

- Although I've done quite a bit of testing, I can't guarantee everything that works on my machine will work on yours. Always back up your data to multiple places to avoid data loss.
- If you find any issues, please contact me... or get your hands dirty and raise a PR!

```

```

## Author

- Tyler Woodfin
  - [GitHub](https://www.github.com/tylerjwoodfin)
  - [Website](http://tyler.cloud)
