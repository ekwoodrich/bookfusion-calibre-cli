.PHONY: debug dist

PLUGIN_VERSION := $(shell python3 scripts/release_metadata.py version)
ifeq ($(strip $(PLUGIN_VERSION)),)
$(error Could not read the canonical Calibre plugin version from __init__.py)
endif

PLUGIN_VERSION_COMPACT := $(subst .,,$(PLUGIN_VERSION))
CLI_BUILD_SUFFIX ?= a
DIST_FILE := dist/BookFusion-cli-$(PLUGIN_VERSION_COMPACT)$(CLI_BUILD_SUFFIX).zip

debug:
	calibre-customize -b .
	calibre-debug -g

dist:
	mkdir -p dist
	if [ -f "$(DIST_FILE)" ]; then rm "$(DIST_FILE)"; fi
	zip -r "$(DIST_FILE)" . -x@.zipignore
