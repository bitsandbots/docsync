# OpenCode Configuration

This project is configured for use with [OpenCode](https://opencode.ai), an open-source AI coding agent.

## Project Instructions

Project-specific instructions are in `AGENTS.md` in the repository root. OpenCode automatically loads these when working in this directory.

## Available Skills

Skills are reusable instruction sets loaded on-demand via the `skill` tool. Global skills are stored in `~/.config/opencode/skills/`.

### Development Workflow

| Skill | Usage | Description |
|-------|-------|-------------|
| `bugfix` | `skill({ name: "bugfix" })` | Structured bug investigation: reproduce → root cause → fix → verify → document |
| `review` | `skill({ name: "review" })` | Code review checklist: correctness, error handling, security, edge cases |
| `ship` | `skill({ name: "ship" })` | Pre-deployment: tests, lint, security, cascade updates, commit |
| `logparse` | `skill({ name: "logparse" })` | Parse log files for errors; optionally investigate and fix |

### Session Management

| Skill | Usage | Description |
|-------|-------|-------------|
| `checkpoint` | `skill({ name: "checkpoint" })` | End-of-session state capture for future context |
| `next` | `skill({ name: "next" })` | Start-of-session: open items, recent commits, suggested first task |
| `pickup` | `skill({ name: "pickup" })` | Resume work on a specific bug/task from memory |
| `retro` | `skill({ name: "retro" })` | Session retrospective: patterns, anti-patterns, learnings |

### Project Health

| Skill | Usage | Description |
|-------|-------|-------------|
| `status` | `skill({ name: "status" })` | Quick health snapshot: tests, lint, deps, git, open items |
| `standup` | `skill({ name: "standup" })` | Generate standup notes from git commits and memory |
| `compact-status` | `skill({ name: "compact-status" })` | Context window usage estimate and compaction recommendation |

### Utilities

| Skill | Usage | Description |
|-------|-------|-------------|
| `summarize` | `skill({ name: "summarize" })` | Compress a file to dense context-friendly summary (<200 words) |
| `treemap` | `skill({ name: "treemap" })` | Project structure map with key symbols |

## Using Skills

When you ask OpenCode to work on something, it may automatically load relevant skills. You can also request skill usage explicitly:

**Example prompts:**
- "Run the review skill on the collector module"
- "Use the bugfix workflow to fix the SSH timeout issue"
- "Checkpoint this session before I leave"
- "What's the project status?"

## Configuration Files

| Path | Purpose |
|------|---------|
| `AGENTS.md` | Project-specific instructions for AI agents |
| `~/.config/opencode/AGENTS.md` | Global instructions (personal preferences) |
| `~/.config/opencode/opencode.json` | OpenCode configuration (provider, model, etc.) |
| `~/.config/opencode/skills/*/SKILL.md` | Skill definitions |

## Skill Anatomy

Each skill is a directory containing `SKILL.md`:

```
~/.config/opencode/skills/bugfix/SKILL.md
```

```yaml
---
name: bugfix
description: Structured bug investigation workflow. Finds root cause, implements fix, verifies with tests.
license: MIT
---

[instructions...]
```

**Naming rules:**
- 1–64 characters
- Lowercase alphanumeric with hyphens
- No leading/trailing hyphens
- Must match directory name

## Extending

### Add Custom Skills

Create `~/.config/opencode/skills/myskill/SKILL.md`:

```yaml
---
name: myskill
description: What this skill does
---

Detailed instructions for the agent...
```

### Project-Local Skills

Project-specific skills go in `.opencode/skills/myskill/SKILL.md` within the repo.

## Claude Code Compatibility

OpenCode reads Claude Code files as fallbacks:

| Claude Code | OpenCode |
|-------------|----------|
| `~/.claude/CLAUDE.md` | `~/.config/opencode/AGENTS.md` |
| `.claude/skills/*/SKILL.md` | `.opencode/skills/*/SKILL.md` |

To disable compatibility:

```bash
export OPENCODE_DISABLE_CLAUDE_CODE=1
```

## Resources

- [OpenCode Documentation](https://opencode.ai/docs/)
- [Skills Reference](https://opencode.ai/docs/skills/)
- [Commands Reference](https://opencode.ai/docs/commands/)
- [GitHub Repository](https://github.com/anomalyco/opencode)