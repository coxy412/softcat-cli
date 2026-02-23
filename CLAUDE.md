# CLAUDE.md — Instructions for Claude Code CLI

## Project Overview

SOFT CAT is a conversational agent spawner CLI. Users describe what they want an agent to do in natural language, and the tool builds, deploys, and monitors it.

**Brand:** SOFT CAT .ai — Smart Outputs From Trained Conversational AI Technology
**Group:** Valori (anonymous collective — always "we" never "I")
**Site:** https://softcat.ai

## Architecture

The tool follows the S.O.F.T.C.A.T pipeline:

1. **Scan** (`softcat/core/scanner.py`) — Parse user's natural language description using Claude. Extract: intent, data sources, output format, cadence/schedule, required tools/APIs.

2. **Orchestrate** (`softcat/core/orchestrator.py`) — Based on scan results, select: which Claude model to use, which MCP servers are needed, which Python libraries to install, what external APIs to connect.

3. **Fabricate** (`softcat/core/fabricator.py`) — Generate the agent: Python script (`agent.py`), prompt template (`prompt.md`), configuration (`config.yaml`). Uses Jinja2 templates from `softcat/templates/`.

4. **Test** (`softcat/core/tester.py`) — Run the generated agent once with sample/mock data. Validate the output matches expected format. Report pass/fail.

5. **Configure** (`softcat/core/configurator.py`) — Set up: cron job or systemd timer, Healthchecks.io ping URL, output directory, environment variables.

6. **Activate** (`softcat/core/activator.py`) — Deploy the agent: install dependencies, register cron/systemd, do first live run, confirm health check ping.

7. **Track** (`softcat/core/tracker.py`) — Ongoing monitoring: read health check status, tail output logs, report agent performance, detect failures and attempt recovery.

## Key Design Decisions

- **Claude API is the brain.** The scan phase sends the user's description to Claude to understand intent. The fabricate phase uses Claude to generate the agent code. The agent itself typically calls Claude at runtime.
- **Agents are self-contained directories** under `~/.softcat/agents/<name>/`. Each has its own code, config, prompt, and outputs.
- **Templates are Jinja2** in `softcat/templates/`. They define the skeleton for different agent types (digest, monitor, transformer, responder).
- **MCP integration** is optional but first-class. If an agent needs web search, file access, or database queries, the orchestrator wires up appropriate MCP servers.
- **Healthchecks.io** is the default monitoring. Agents ping on success, alert on failure.
- **Cat-themed CLI** via Click. Commands: spawn, litter, purr, feed, nap, wake, hiss, groom, adopt, meow.

## Tech Stack

- Python 3.10+
- Click (CLI framework)
- Anthropic SDK (Claude API)
- Jinja2 (agent templating)
- PyYAML (configuration)
- Rich (terminal output — spinners, tables, colours)
- Crontab (scheduling)
- httpx (HTTP requests, health checks)

## Code Style

- Type hints everywhere
- Docstrings on public functions
- f-strings over .format()
- Use Rich for all terminal output — no bare print()
- Error messages should be helpful and cat-themed where appropriate
- Keep functions small and focused
- Use async where I/O is involved

## File Structure

```
softcat-cli/
├── CLAUDE.md              ← you are here
├── README.md
├── pyproject.toml
├── softcat/
│   ├── __init__.py
│   ├── cli.py             ← Click CLI entry point
│   ├── config.py          ← Global config management
│   ├── core/
│   │   ├── __init__.py
│   │   ├── scanner.py     ← S — parse natural language
│   │   ├── orchestrator.py ← O — select model/tools
│   │   ├── fabricator.py  ← F — generate agent code
│   │   ├── tester.py      ← T — validate agent
│   │   ├── configurator.py ← C — set up deployment
│   │   ├── activator.py   ← A — deploy agent
│   │   └── tracker.py     ← T — monitor agent
│   ├── agents/
│   │   ├── __init__.py
│   │   └── manager.py     ← CRUD for spawned agents
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── registry.py    ← available MCP servers
│   └── templates/
│       ├── base_agent.py.j2
│       ├── digest_agent.py.j2
│       ├── monitor_agent.py.j2
│       ├── transformer_agent.py.j2
│       └── prompt.md.j2
├── tests/
│   ├── test_scanner.py
│   ├── test_orchestrator.py
│   ├── test_fabricator.py
│   └── test_cli.py
├── docs/
│   ├── architecture.md
│   ├── templates.md
│   └── mcp-integration.md
└── examples/
    ├── hn-digest.yaml
    ├── arxiv-monitor.yaml
    └── site-content-bot.yaml
```

## Testing

```bash
pytest tests/ -v
```

## Common Tasks

### Adding a new agent template
1. Create `softcat/templates/<name>_agent.py.j2`
2. Register it in `softcat/core/orchestrator.py` template selection logic
3. Add an example in `examples/`

### Adding a new CLI command
1. Add the Click command in `softcat/cli.py`
2. Keep the cat theme consistent
3. Use Rich for output

### Adding MCP server support
1. Register in `softcat/mcp/registry.py`
2. Add connection logic
3. Update orchestrator to select it when relevant

## Voice & Copy

All user-facing text (CLI output, errors, docs) should:
- Use "we" not "I"
- Be concise and slightly playful
- Cat puns are acceptable but not mandatory
- Technical accuracy over personality — never sacrifice clarity for a joke
