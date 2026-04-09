# DocSync Tech Stack

## Runtime Dependencies

### Core Libraries

| Package | Version | Purpose |
|---------|---------|---------|
| `click` | >=8.0 | CLI framework |
| `pyyaml` | >=6.0 | YAML config parsing |
| `jinja2` | >=3.0 | Template rendering |
| `markdown-it-py` | >=3.0 | Markdown → HTML |
| `zstandard` | >=0.21 | Zstd compression for backups |
| `flask` | >=3.0 | Admin web UI |

### System Dependencies

| Binary | Purpose |
|--------|---------|
| `rsync` | File synchronization (local and remote) |
| `ssh` | Secure shell for remote source access |
| `inotifywait` (optional) | File change monitoring for `docsync watch` |
| `gzip` | Alternative compression for backups |
| `zstd` | Command-line tool for zstd compression |

## Development Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Unit and integration tests |
| `build` | Package building |
| `wheel` | Wheel distribution |

## Python Version

- **Minimum**: 3.11
- **Tested**: 3.13

## Frontend Technologies (Static Site)

| Technology | Purpose |
|------------|---------|
| Vanilla JavaScript | Client-side interactivity |
| Lunr.js | Client-side full-text search |
| CSS Grid | Responsive layout |

## Browser Compatibility

- Chrome/Edge (Chromium) 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Mobile)

## Build/Deployment Stack

| Tool | Purpose |
|------|---------|
| `setuptools` | Python packaging |
| `pip` | Package installation |
| `systemd` | Service/timer management |
| `Apache` (optional) | Web server vhost |

## Database (Runtime)

- **SQLite** (via `chromadb` dependency - not directly used by DocSync, but available for RAG features in related CoreAI project)

## Security Considerations

- **XSS prevention**: `html=False` in markdown-it-py renderer
- **Path traversal protection**: `safe_path()` in web.py
- **Environment variables**: `.env` file for sensitive credentials (gitignored)
- **No root in service**: `NoNewPrivileges=true` in systemd units

## Versioning

- **Current version**: 0.1.0
- **Package name**: `docsync`
- **Entry point**: `docsync.cli:main`
