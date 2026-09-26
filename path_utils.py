__copyright__ = '2026, Eliot Woodrich'
__license__ = 'GPL v3'

import os
import sys


def win_long_path(file_path):
    if not file_path or sys.platform != 'win32':
        return file_path

    normalized = os.path.abspath(file_path)
    if normalized.startswith('\\\\?\\'):
        return normalized

    if normalized.startswith('\\\\'):
        return '\\\\?\\UNC\\' + normalized[2:]

    return '\\\\?\\' + normalized
