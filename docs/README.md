# DocSync Documentation

## Overview

DocSync is a documentation wiki generator and file backup tool. It collects markdown files from local and remote sources, renders them into a static site, and optionally backs up source directories.

## Quick Links

- **[CLI Reference](cli.md)** - All `docsync` commands and options
- **[OpenCode Configuration](opencode.md)** - Skills and commands for AI-assisted development

## Installation

```bash
# Install requirements
sudo apt install rsync inotify-tools  # Remote sync and watch mode

# Install Python package
pip install .

# Initialize config
docsync init

# Edit config
nano ~/.config/docsync/docsync.yaml

# Validate
docsync check
```

## Basic Usage

```bash
# Full sync (all sources)
docsync sync

# Sync single source
docsync sync --source "My Project"

# Watch mode (auto-sync on file changes)
docsync watch --debounce 3

# Start dev server
docsync serve --port 8484

# Run sync + backup
docsync all
```

## Documentation License

MIT License - CoreConduit