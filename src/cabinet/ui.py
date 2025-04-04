"""
ui module for Cabinet

provides interactive command-line interface components using prompt_toolkit.
includes functions for list selection, html rendering, and confirmation dialogs.
"""

from typing import List, Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import radiolist_dialog, yes_no_dialog

def list_selection(items: List[str], prompt: str = "Make a Selection:") -> int:
    """
    display a list of items and return the index of the selected item

    args:
        items: list of strings to display
        prompt: optional prompt text to show above the list
    returns:
        int: index of the selected item
    """
    # create a list of tuples for radiolist_dialog
    choices = [(i, item) for i, item in enumerate(items)]

    # show the dialog and get the result
    result = radiolist_dialog(
        title=prompt,
        values=choices
    ).run()

    # return the index of the selected item
    return result if result is not None else -1

def render_html(html_text: str) -> None:
    """
    render html text using prompt_toolkit's html formatter

    args:
        html_text: string containing html markup
    """
    # create a prompt session
    session = PromptSession()

    # render the html text
    formatted_text = HTML(html_text)

    # display the formatted text
    session.prompt(formatted_text)

def confirmation(
    prompt: str = "Are you sure?",
    title: str = "Confirmation",
) -> bool:
    """
    show a confirmation dialog with two options

    args:
        prompt: text to display in the dialog
        title: title of the dialog

    returns:
        bool: True if option1 is selected, False if option2 is selected
    """

    # show a yes/no dialog
    result = yes_no_dialog(
        title=title,
        text=prompt
    ).run()

    return result
