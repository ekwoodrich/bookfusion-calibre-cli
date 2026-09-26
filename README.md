# BookFusion Calibre Plugin

This fork adds a command-line interface to the official BookFusion Calibre plugin so scripts and scheduled jobs can upload either the whole library or selected books by Calibre ID. The original plugin exposed syncing only through its graphical interface, which made those operations difficult to automate. The CLI invokes the plugin's existing upload flow and saved settings, allowing automation to perform the same sync operations a user can start in Calibre.

## CLI

``` shell
calibre-debug -r "BookFusion Plugin CLI" -- sync-all
calibre-debug -r "BookFusion Plugin CLI" -- sync-all --library-name Library-DXP
calibre-debug -r "BookFusion Plugin CLI" -- sync-selected --ids 123
calibre-debug -r "BookFusion Plugin CLI" -- sync-selected --ids 123,456 --library-name Library-DXP
```

This runs the existing "Sync all books" flow against the current calibre
library using the saved BookFusion plugin settings for that calibre instance.
If `--library-name` is omitted, the plugin uses the previously selected
calibre library. `sync-selected` accepts one or more calibre book IDs.

Debug:

``` shell
make debug
```

Package:

``` shell
make dist
```

(creates `dist/BookFusion-cli-081a.zip` for plugin version `(0, 8, 1)` with the default `a` suffix). Set `CLI_BUILD_SUFFIX` to choose a different fork build letter:

``` shell
make dist CLI_BUILD_SUFFIX=b
```

The archive's canonical Calibre plugin version is read directly from `BookFusionPlugin.version` in `__init__.py`; packaging and release automation do not modify it.

## GitHub releases

Every push to `master` (including a merged PR) builds and publishes a GitHub release. The release tag and title use `cli-<canonical-version><suffix>`, for example `cli-0.8.2a`, while the archive uses the compact version, for example `BookFusion-cli-082a.zip`.

The suffix starts at `a` for each canonical plugin version and advances through `b`, `c`, and so on based on existing release tags. If `__init__.py` changes to a new canonical version, the next release starts at suffix `a`; the plugin version itself remains exactly as specified in `__init__.py`.
