#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import os.path
import re
import py_compile


def _traverse_dir(path):
    for pname in os.listdir(path):
        fname = os.path.join(path, pname)
        if os.path.isdir(fname) and not os.path.islink(fname):
            _traverse_dir(fname)
        else:
            if re.match('^[\w\-_]+\.py$', pname):
                fcname = fname + 'c'
                try:
                    fmtime = os.stat(fname).st_mtime
                except OSError as err:
                    fmtime = 0
                try:
                    fcmtime = os.stat(fcname).st_mtime
                except OSError as err:
                    fcmtime = 0
                if fmtime >= fcmtime:
                    sys.stdout.write('Compiling file "%s" ... ' % fname)
                    py_compile.compile(fname)
                    sys.stdout.write('done\n')


def do():
    _traverse_dir('config')
    _traverse_dir('util')
    _traverse_dir('modules')
    _traverse_dir('handlers')
    _traverse_dir('templates')


if __name__ == '__main__':
    do()
