# DocSync Documentation

DocSync is a documentation wiki and backup tool that aggregates markdown files from local and remote sources into a searchable static site with compressed, incremental backups.

## Quick Start

```bash
# Install
sudo bash install.sh

# Initialize config
docsync init

# Edit config
nano ~/.config/docsync/docsync.yaml

# Validate
docsync check

# First sync
docsync sync

# Start web server
docsync serve --port 8484
```

Browse to `http://localhost:8484` to view your documentation site.

## Documentation

| Document | Description |
|----------|-------------|
| [Overview](overview.md) | Project purpose, goals, and key features |
| [Architecture](architecture.md) | High-level design and data flow |
| [Tech Stack](techstack.md) | Dependencies, Python version, and tools |
| [Setup & Usage](setup.md) | Installation and running instructions |
| [CLI Reference](cli-reference.md) | All commands and options |
| [Modules](modules.md) | Core module documentation |
| [Config Schema](config-schema.md) | Configuration file reference |
| [Backup Subsystem](backup-subsystem.md) | Backup features and usage |

## Commands

| Command | Description |
|---------|-------------|
| `docsync init` | Generate starter config |
| `docsync check` | Validate config and test connectivity |
| `docsync sync` | Collect docs and generate site |
| `docsync status` | Show manifest statistics |
| `docsync serve` | Start web server |
| `docsync add [PATH]` | Add new source |
| `docsync watch` | Watch files for changes |
| `docsync all` | Run sync + backup |
| `docsync backup run` | Run backup |
| `docsync backup list` | List snapshots |
| `docsync backup status` | Show backup health |
| `docsync backup verify` | Verify integrity |
| `docsync backup size` | Show storage usage |
| `docsync backup restore` | Restore snapshot |

## Project Info

- **Version**: 0.1.0
- **License**: MIT
- **Author**: CoreConduit
- **Python**: 3.11+

## Contact

For issues or questions, please check the documentation or open an issue on GitHub.
