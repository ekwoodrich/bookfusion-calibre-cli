# BookFusion Calibre Plugin

CLI:

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

(creates `dist/BookFusion.zip`)
