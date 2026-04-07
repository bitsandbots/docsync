"""DocSync — Project Documentation Wiki & File Backup Tool.

DocSync aggregates markdown documentation from local and remote sources into
a searchable static site with compressed, incremental backups.

Usage:
    docsync init            # Create default config
    docsync check           # Validate config and test connectivity
    docsync sync            # Collect → parse → generate site
    docsync backup run      # Run backup for all sources
    docsync serve           # Start web server

Config: ~/.config/docsync/docsync.yaml
Cache:  ~/.cache/docsync/
"""

__version__ = "0.1.0"
__author__ = "CoreConduit"
__license__ = "MIT"

__all__ = [
    "__version__",
    "__author__",
    "__license__",
]
