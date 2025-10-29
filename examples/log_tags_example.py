#!/usr/bin/env python3
"""
Example demonstrating the use of tags in logging and log_query function.
"""
from cabinet import Cabinet

# Initialize Cabinet
cab = Cabinet()

# Example 1: Logging with single tag
cab.log("Checked weather successfully", tags=["weather"])

# Example 2: Logging with multiple tags
cab.log("Starting Borg Backup...", tags=["backup", "start"])
cab.log("Pruning repository", tags=["backup", "prune"])
cab.log("Compacting repository", tags=["backup", "compact"])

# Example 3: Logging without tags (backward compatible)
cab.log("Regular log message without tags")

# Example 4: Query today's logs by tag (log_file is optional)
results = cab.log_query(tags=["backup"])
for result in results:
    print(result)

# Example 5: Query today's logs by multiple criteria
results = cab.log_query(tags=["backup"], level="INFO", message="repository")
for result in results:
    print(result)

# Example 6: Query today's logs by path (fuzzy search)
results = cab.log_query(path="cabinet")
for result in results:
    print(result)

# Example 7: Query specific date's log file
results = cab.log_query("LOG_DAILY_2025-10-28.log", tags=["backup"])
for result in results:
    print(result)
