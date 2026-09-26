#!/usr/bin/env python3
"""Read the canonical Calibre plugin version and select a fork build suffix."""

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_FILE = REPO_ROOT / '__init__.py'


def canonical_version():
    tree = ast.parse(PLUGIN_FILE.read_text(encoding='utf-8'), filename=str(PLUGIN_FILE))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != 'BookFusionPlugin':
            continue
        for statement in node.body:
            if not isinstance(statement, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == 'version' for target in statement.targets):
                continue
            value = ast.literal_eval(statement.value)
            if (
                isinstance(value, tuple)
                and len(value) == 3
                and all(isinstance(part, int) and part >= 0 for part in value)
            ):
                return '.'.join(str(part) for part in value)
            raise ValueError('BookFusionPlugin.version must be a three-part nonnegative integer tuple')
    raise ValueError('Could not find BookFusionPlugin.version in __init__.py')


def suffix_number(suffix):
    value = 0
    for char in suffix:
        value = value * 26 + ord(char) - ord('a') + 1
    return value


def suffix_letters(value):
    parts = []
    while value:
        value, remainder = divmod(value - 1, 26)
        parts.append(chr(ord('a') + remainder))
    return ''.join(reversed(parts))


def next_suffix(commit):
    if not commit:
        raise ValueError('next-suffix requires --commit with the current commit SHA')

    version = canonical_version()
    tag_prefix = 'cli-%s' % version
    pattern = re.compile(re.escape(tag_prefix) + r'([a-z]+)$')
    existing = []
    for tag in subprocess.check_output(
        ['git', 'tag', '--list', tag_prefix + '*'], cwd=REPO_ROOT, text=True
    ).splitlines():
        match = pattern.fullmatch(tag)
        if not match:
            continue
        suffix = match.group(1)
        resolved = subprocess.run(
            ['git', 'rev-parse', '--verify', '--quiet', '%s^{commit}' % tag],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if resolved.returncode == 0:
            existing.append((suffix_number(suffix), suffix, resolved.stdout.strip()))

    same_commit = [item for item in existing if item[2] == commit]
    if same_commit:
        return max(same_commit)[1]
    highest = max((item[0] for item in existing), default=0)
    return suffix_letters(highest + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('version', 'next-suffix'))
    parser.add_argument('--commit', help='commit SHA for idempotent release retries')
    args = parser.parse_args()
    try:
        output = canonical_version() if args.command == 'version' else next_suffix(args.commit)
    except (OSError, SyntaxError, ValueError, subprocess.CalledProcessError) as error:
        print('release metadata error: %s' % error, file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
