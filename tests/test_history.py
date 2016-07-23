# -*- coding: utf-8 -*-
"""Tests the xonsh history."""
# pylint: disable=protected-access
# TODO: Remove the following pylint directive when it correctly handles calls
# to nose assert_xxx functions.
# pylint: disable=no-value-for-parameter
from __future__ import unicode_literals, print_function
import io
import os
import sys
import shlex

from xonsh.lazyjson import LazyJSON
from xonsh.history import History, _hist_create_parser, _hist_parse_args
from xonsh import history

import pytest


@pytest.yield_fixture
def hist():
    h = History(filename='xonsh-HISTORY-TEST.json', here='yup', sessionid='SESSIONID', gc=False)
    yield h
    os.remove(h.filename)


def test_hist_init(hist):
    """Test initialization of the shell history."""
    with LazyJSON(hist.filename) as lj:
        obs = lj['here']
    assert 'yup' == obs


def test_hist_append(hist, xonsh_builtins):
    """Verify appending to the history works."""
    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = set()
    hf = hist.append({'joco': 'still alive'})
    assert hf is None
    assert 'still alive' == hist.buffer[0]['joco']


def test_hist_flush(hist, xonsh_builtins):
    """Verify explicit flushing of the history works."""
    hf = hist.flush()
    assert hf is None
    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = set()
    hist.append({'joco': 'still alive'})
    hf = hist.flush()
    assert hf is not None
    while hf.is_alive():
        pass
    with LazyJSON(hist.filename) as lj:
        obs = lj['cmds'][0]['joco']
    assert 'still alive' == obs


def test_cmd_field(hist, xonsh_builtins):
    # in-memory
    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = set()
    hf = hist.append({'rtn': 1})
    assert hf is None
    assert 1 == hist.rtns[0]
    assert 1 == hist.rtns[-1]
    assert None == hist.outs[-1]
    # slice
    assert [1] == hist.rtns[:]
    # on disk
    hf = hist.flush()
    assert hf is not None
    assert 1 == hist.rtns[0]
    assert 1 == hist.rtns[-1]
    assert None == hist.outs[-1]

def run_show_cmd(hist_args, commands, base_idx=0, step=1):
    """Run and evaluate the output of the given show command."""
    stdout = sys.stdout
    stdout.seek(0, io.SEEK_SET)
    stdout.truncate()
    history.history_main(hist_args)
    stdout.seek(0, io.SEEK_SET)
    hist_lines = stdout.readlines()
    assert len(commands) == len(hist_lines)
    for idx, (cmd, actual) in enumerate(zip(commands, hist_lines)):
        expected = ' {:d}: {:s}\n'.format(base_idx + idx * step, cmd)
        assert expected == actual

def test_show_cmd(hist, xonsh_builtins):
    """Verify that CLI history commands work."""
    cmds = ['ls', 'cat hello kitty', 'abc', 'def', 'touch me', 'grep from me']
    sys.stdout = io.StringIO()
    xonsh_builtins.__xonsh_history__ = hist
    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = set()
    for ts,cmd in enumerate(cmds):  # populate the shell history
        hist.append({'inp': cmd, 'rtn': 0, 'ts':(ts+1, ts+1.5)})

    # Verify an implicit "show" emits show history
    run_show_cmd([], cmds)

    # Verify an explicit "show" with no qualifiers emits
    # show history.
    run_show_cmd(['show'], cmds)

    # Verify an explicit "show" with a reversed qualifier
    # emits show history in reverse order.
    run_show_cmd(['show', '-r'], list(reversed(cmds)),
                             len(cmds) - 1, -1)

    # Verify that showing a specific history entry relative to
    # the start of the history works.
    run_show_cmd(['show', '0'], [cmds[0]], 0)
    run_show_cmd(['show', '1'], [cmds[1]], 1)

    # Verify that showing a specific history entry relative to
    # the end of the history works.
    run_show_cmd(['show', '-2'], [cmds[-2]],
                           len(cmds) - 2)

    # Verify that showing a history range relative to the start of the
    # history works.
    run_show_cmd(['show', '0:2'], cmds[0:2], 0)
    run_show_cmd(['show', '1::2'], cmds[1::2], 1, 2)

    # Verify that showing a history range relative to the end of the
    # history works.
    run_show_cmd(['show', '-2:'],
                           cmds[-2:], len(cmds) - 2)
    run_show_cmd(['show', '-4:-2'],
                           cmds[-4:-2], len(cmds) - 4)

    sys.stdout = sys.__stdout__


def test_histcontrol(hist, xonsh_builtins):
    """Test HISTCONTROL=ignoredups,ignoreerr"""

    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = 'ignoredups,ignoreerr'
    assert len(hist.buffer) == 0

    # An error, buffer remains empty
    hist.append({'inp': 'ls foo', 'rtn': 2})
    assert len(hist.buffer) == 0

    # Success
    hist.append({'inp': 'ls foobazz', 'rtn': 0})
    assert len(hist.buffer) == 1
    assert 'ls foobazz' == hist.buffer[-1]['inp']
    assert 0 == hist.buffer[-1]['rtn']

    # Error
    hist.append({'inp': 'ls foo', 'rtn': 2})
    assert len(hist.buffer) == 1
    assert 'ls foobazz' == hist.buffer[-1]['inp']
    assert 0 == hist.buffer[-1]['rtn']

    # File now exists, success
    hist.append({'inp': 'ls foo', 'rtn': 0})
    assert len(hist.buffer) == 2
    assert 'ls foo' == hist.buffer[-1]['inp']
    assert 0 == hist.buffer[-1]['rtn']

    # Success
    hist.append({'inp': 'ls', 'rtn': 0})
    assert len(hist.buffer) == 3
    assert 'ls' == hist.buffer[-1]['inp']
    assert 0 == hist.buffer[-1]['rtn']

    # Dup
    hist.append({'inp': 'ls', 'rtn': 0})
    assert len(hist.buffer) == 3

    # Success
    hist.append({'inp': '/bin/ls', 'rtn': 0})
    assert len(hist.buffer) == 4
    assert '/bin/ls' == hist.buffer[-1]['inp']
    assert 0 == hist.buffer[-1]['rtn']

    # Error
    hist.append({'inp': 'ls bazz', 'rtn': 1})
    assert len(hist.buffer) == 4
    assert '/bin/ls' == hist.buffer[-1]['inp']
    assert 0 == hist.buffer[-1]['rtn']

    # Error
    hist.append({'inp': 'ls bazz', 'rtn': -1})
    assert len(hist.buffer) == 4
    assert '/bin/ls' == hist.buffer[-1]['inp']
    assert 0 == hist.buffer[-1]['rtn']


@pytest.mark.parametrize('args', [ '-h', '--help', 'show -h', 'show --help'])
def test_parse_args_help(args, capsys):
    with pytest.raises(SystemExit):
        args = _hist_parse_args(shlex.split(args))
    assert 'show this help message and exit' in capsys.readouterr()[0]


@pytest.mark.parametrize('args, exp', [
    ('', ('show', 'session', [])),
    ('show', ('show', 'session', [])),
    ('show session', ('show', 'session', [])),
    ('show session 15', ('show', 'session', ['15'])),
    ('show bash 3:5 15:66', ('show', 'bash', ['3:5', '15:66'])),
    ('show zsh 3 5:6 16 9:3', ('show', 'zsh', ['3', '5:6', '16', '9:3'])),
    ])
def test_parser_show(args, exp):
    args = _hist_parse_args(shlex.split(args))
    action, session, slices = exp
    assert args.action == action
    assert args.session == session
    assert args.slices == slices
