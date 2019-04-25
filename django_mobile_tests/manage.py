#!/usr/bin/env python
# vim:fileencoding=utf-8
import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'django_mobile_tests.settings'
parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, parent)


if __name__ == '__main__':
    from django.core.management import execute_from_command_line
    execute_from_command_line()

