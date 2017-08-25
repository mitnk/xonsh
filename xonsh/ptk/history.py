# -*- coding: utf-8 -*-
"""History object for use with prompt_toolkit."""
import builtins
from threading import Thread

import prompt_toolkit.history


class PromptToolkitHistory(prompt_toolkit.history.History):
    """History class that implements the prompt-toolkit history interface
    with the xonsh backend.
    """

    def __init__(self, load_prev=True, *args, **kwargs):
        """Initialize history object."""
        super().__init__()
        self.strings = []
        if load_prev:
            PromptToolkitHistoryAdder(self)

    def append(self, entry):
        """Append new entry to the history."""
        self.strings.append(entry)

    def __getitem__(self, index):
        return self.strings[index]

    def __len__(self):
        return len(self.strings)

    def __iter__(self):
        return iter(self.strings)


class PromptToolkitHistoryAdder(Thread):

    def __init__(self, ptkhist, *args, **kwargs):
        """Thread responsible for adding inputs from history to the current
        prompt-toolkit history instance. May wait for the history garbage
        collector to finish.
        """
        super(PromptToolkitHistoryAdder, self).__init__(*args, **kwargs)
        self.daemon = True
        self.ptkhist = ptkhist
        self.start()

    def run(self):
        hist = builtins.__xonsh_history__
        if hist is None:
            return
        buf = None
        ptkhist = self.ptkhist
        for cmd in hist.all_items():
            line = cmd['inp'].rstrip()
            if len(ptkhist) == 0 or line != ptkhist[-1]:
                ptkhist.append(line)
