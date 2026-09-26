__copyright__ = '2026, Eliot Woodrich'
__license__ = 'GPL v3'

import sys
from os import path

from PyQt5.Qt import QCoreApplication, QObject, QThread

from calibre.constants import config_dir
from calibre.library import current_library_path, db as open_library

from calibre_plugins.bookfusion.check_worker import CheckWorker
from calibre_plugins.bookfusion.config import prefs
from calibre_plugins.bookfusion.logger import Logger
from calibre_plugins.bookfusion.upload_manager import UploadManager


USAGE = '''Usage:
  calibre-debug -r "BookFusion Plugin CLI" -- sync-all
  calibre-debug -r "BookFusion Plugin CLI" -- sync-all --library-name Library-DXP
  calibre-debug -r "BookFusion Plugin CLI" -- sync-selected --ids 123
  calibre-debug -r "BookFusion Plugin CLI" -- sync-selected --ids 123,456 --library-name Library-DXP

Runs the BookFusion "Sync all books" action using the saved plugin settings
for the current calibre library.
'''


class CliSyncRunner(QObject):
    def __init__(self, app, db, library_path, book_ids, sync_label, stdout, stderr):
        QObject.__init__(self)

        self.app = app
        self.db = db
        self.library_path = library_path
        self.initial_book_ids = list(book_ids)
        self.sync_label = sync_label
        self.stdout = stdout
        self.stderr = stderr
        self.logger = Logger(self._log_path())

        self.worker = None
        self.worker_thread = None
        self.book_ids = []
        self.valid_book_ids = []
        self.books_count = 0
        self.limits = {}
        self.exit_code = 0
        self.summary = {
            'uploaded': 0,
            'updated': 0,
            'skipped': 0,
            'failed': 0,
        }

    def start(self):
        self.book_ids = list(self.initial_book_ids)
        self._write(self.stdout, 'Starting BookFusion {} for library: {}\n'.format(self.sync_label, self.library_path))
        self._write(self.stdout, 'Found {} calibre books to process.\n'.format(len(self.book_ids)))

        self.worker_thread = QThread(self)
        self.worker = CheckWorker(self.db, self.logger, self.book_ids)
        self.worker.finished.connect(self.finish_check)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.progress.connect(self.update_progress)
        self.worker.limitsAvailable.connect(self.apply_limits)
        self.worker.resultsAvailable.connect(self.apply_results)
        self.worker.aborted.connect(self.abort)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.start)
        self.worker_thread.start()

    def finish_check(self):
        self._wait_for_worker_thread()

        if not self.valid_book_ids:
            self._write(self.stdout, 'No supported books found to sync.\n')
            self.finish()
            return

        is_filesize_exceeded = len(self.valid_book_ids) < self.books_count
        is_total_books_exceeded = self.limits.get('total_books') and self.books_count > self.limits['total_books']

        if (is_filesize_exceeded or is_total_books_exceeded) and self.limits.get('message'):
            self.exit_code = 2
            self._write(self.stderr, self.limits['message'] + '\n')
            self.finish()
            return

        self.start_sync()

    def start_sync(self):
        book_ids = list(self.valid_book_ids)
        if self.limits.get('total_books'):
            book_ids = book_ids[:self.limits['total_books']]

        self.book_ids = book_ids
        self._write(self.stdout, 'Syncing {} supported books.\n'.format(len(book_ids)))

        self.worker_thread = QThread(self)
        self.worker = UploadManager(self.db, self.logger, book_ids, False)
        self.worker.finished.connect(self.finish_sync)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.progress.connect(self.update_progress)
        self.worker.started.connect(self.log_start)
        self.worker.skipped.connect(self.log_skip)
        self.worker.failed.connect(self.log_fail)
        self.worker.uploaded.connect(self.log_upload)
        self.worker.updated.connect(self.log_update)
        self.worker.aborted.connect(self.abort)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.start)
        self.worker_thread.start()

    def finish_sync(self):
        self._wait_for_worker_thread()
        self._write(
            self.stdout,
            'Sync complete. uploaded={uploaded} updated={updated} skipped={skipped} failed={failed}\n'.format(**self.summary)
        )
        self.finish()

    def apply_limits(self, limits):
        self.limits = limits
        self.logger.info('CLI limits: {}'.format(limits))

    def apply_results(self, books_count, valid_ids):
        self.books_count = books_count
        self.valid_book_ids = list(valid_ids)
        self.logger.info('CLI check results: books_count={}; valid_ids={}'.format(books_count, valid_ids))

    def update_progress(self, progress):
        if progress is None:
            return

        current = progress + 1
        if isinstance(self.worker, UploadManager):
            total = len(self.book_ids)
            phase = 'Synchronizing'
        else:
            total = len(self.book_ids)
            phase = 'Preparing'
        self._write(self.stdout, '{}... {} of {}\n'.format(phase, current, total))

    def log_start(self, book_id):
        title = self.db.get_proxy_metadata(book_id).title
        self._write(self.stdout, 'Starting: {}\n'.format(title))

    def log_skip(self, book_id):
        self.summary['skipped'] += 1
        self._write_result(book_id, 'skipped')

    def log_fail(self, book_id, msg):
        self.summary['failed'] += 1
        self._write_result(book_id, 'failed ({})'.format(msg))

    def log_upload(self, book_id):
        self.summary['uploaded'] += 1
        self._write_result(book_id, 'uploaded')

    def log_update(self, book_id):
        self.summary['updated'] += 1
        self._write_result(book_id, 'updated')

    def abort(self, error):
        if not self.exit_code:
            self.exit_code = 1
        self._write(self.stderr, error + '\n')
        self.finish()

    def finish(self):
        self._wait_for_worker_thread()
        self.app.quit()

    def _wait_for_worker_thread(self):
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
        self.worker = None

    def _write_result(self, book_id, result):
        title = self.db.get_proxy_metadata(book_id).title
        self._write(self.stdout, '{}: {}\n'.format(title, result))

    def _log_path(self):
        import os
        return os.path.join(self.library_path, 'bookfusion_sync.log')

    def _write(self, stream, msg):
        stream.write(msg)
        stream.flush()


def run_cli(args, stdout=None, stderr=None):
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    args = list(args)

    if args and args[0] == 'BookFusion Plugin CLI':
        args = args[1:]

    if not args or args[0] in ('-h', '--help', 'help'):
        stdout.write(USAGE)
        stdout.flush()
        return 0

    if args[0] not in ('sync-all', 'sync-selected'):
        stderr.write('Unknown command: {}\n\n{}'.format(args[0], USAGE))
        stderr.flush()
        return 1

    try:
        command, book_ids, library_name = parse_command_args(args)
    except ValueError as err:
        stderr.write(str(err) + '\n\n' + USAGE)
        stderr.flush()
        return 1

    if not prefs['api_key']:
        stderr.write('BookFusion API key is not configured for this calibre instance.\n')
        stderr.flush()
        return 1

    try:
        library_path = resolve_library_path(library_name)
    except ValueError as err:
        stderr.write(str(err) + '\n')
        stderr.flush()
        return 1

    if not library_path:
        stderr.write('Could not determine the current calibre library path.\n')
        stderr.flush()
        return 1

    app = QCoreApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QCoreApplication(['bookfusion-cli'])

    library_db = open_library(library_path)
    try:
        db_api = library_db.new_api
        try:
            if command == 'sync-all':
                book_ids = list(db_api.all_book_ids())
            else:
                book_ids = resolve_selected_book_ids(db_api, book_ids)
        except ValueError as err:
            stderr.write(str(err) + '\n')
            stderr.flush()
            return 1

        runner = CliSyncRunner(app, db_api, library_path, book_ids, command, stdout, stderr)
        runner.start()
        app.exec_()
        return runner.exit_code
    finally:
        library_db.close()


def parse_command_args(args):
    command = args[0]
    library_name = None
    ids = None

    index = 1
    while index < len(args):
        arg = args[index]
        if arg == '--library-name':
            index += 1
            if index >= len(args):
                raise ValueError('Missing value for --library-name')
            library_name = args[index]
        elif arg.startswith('--library-name='):
            library_name = arg.split('=', 1)[1]
        elif arg == '--ids':
            index += 1
            if index >= len(args):
                raise ValueError('Missing value for --ids')
            ids = parse_book_ids(args[index])
        elif arg.startswith('--ids='):
            ids = parse_book_ids(arg.split('=', 1)[1])
        else:
            raise ValueError('Unexpected arguments: {}'.format(' '.join(args[1:])))
        index += 1

    if command == 'sync-selected':
        if not ids:
            raise ValueError('sync-selected requires --ids with one or more calibre book IDs')
    elif ids is not None:
        raise ValueError('sync-all does not accept --ids')

    return command, ids, library_name


def parse_book_ids(raw_value):
    ids = []
    for item in raw_value.split(','):
        item = item.strip()
        if not item:
            continue
        try:
            ids.append(int(item))
        except ValueError:
            raise ValueError('Invalid calibre book ID: {}'.format(item))

    if not ids:
        raise ValueError('Expected at least one calibre book ID in --ids')

    return ids


def resolve_selected_book_ids(db_api, requested_ids):
    all_ids = set(db_api.all_book_ids())
    missing = [book_id for book_id in requested_ids if book_id not in all_ids]
    if missing:
        raise ValueError('Book IDs not found in library: {}'.format(', '.join(str(book_id) for book_id in missing)))

    return requested_ids


def resolve_library_path(library_name=None):
    current_path = current_library_path()
    if library_name is None:
        return current_path

    candidates = []
    if current_path:
        candidates.append(current_path)

    candidates.extend(read_known_library_paths())

    normalized_name = normalize_library_name(library_name)
    for candidate in unique_paths(candidates):
        if normalize_library_name(candidate) == normalized_name:
            return candidate

    raise ValueError('Could not find a calibre library named "{}".'.format(library_name))


def read_known_library_paths():
    candidates = []

    for filename, keys in (
        ('global.py.json', ['library_path']),
        ('dynamic.pickle.json', ['choose library location']),
    ):
        config = read_json_file(path.join(config_dir, filename))
        for key in keys:
            value = config.get(key)
            if value:
                candidates.append(value)

    gui_config = read_json_file(path.join(config_dir, 'gui.json'))
    usage_stats = gui_config.get('library_usage_stats') or {}
    candidates.extend(usage_stats.keys())

    return candidates


def read_json_file(file_path):
    import json

    try:
        with open(file_path, 'r') as file_obj:
            return json.load(file_obj)
    except (IOError, OSError, ValueError):
        return {}


def normalize_library_name(library_path):
    return path.basename(path.normpath(library_path)).lower()


def unique_paths(paths):
    seen = set()
    for candidate in paths:
        normalized = path.normcase(path.normpath(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        yield candidate
