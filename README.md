# 🐱 SOFT CAT

**Smart Outputs From Trained Conversational AI Technology**

A conversational agent spawner. You describe what you want in plain language. The cat builds, deploys, and monitors an agent for you.

Every agent SOFT CAT creates is itself a SOFT CAT — a smart output from trained conversational AI technology. The acronym is recursive. The product is the name.

---

## The Pipeline: S.O.F.T.C.A.T

| Stage | Letter | What happens |
|-------|--------|-------------|
| **S**can | S | Parse natural language request — intent, data sources, cadence |
| **O**rchestrate | O | Select model, MCP servers, tools for the job |
| **F**abricate | F | Generate agent code, config, prompts, connections |
| **T**est | T | Run against sample data, validate outputs |
| **C**onfigure | C | Set up deployment — cron, health checks, alerts |
| **A**ctivate | A | Deploy live |
| **T**rack | T | Monitor, log, self-heal |

## Install

```bash
pip install softcat-ai
```

Or from source:

```bash
git clone https://github.com/valori-collective/softcat.git
cd softcat
pip install -e .
```

## Quick Start

```bash
# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Spawn your first agent
softcat spawn "watch HackerNews for AI news, summarise top 5 daily, save as markdown"

# See what's running
softcat litter

# Check on an agent
softcat purr hn-digest

# See its outputs
softcat feed hn-digest
```

## CLI Commands

```bash
softcat spawn "..."       # create agent from natural language description
softcat litter             # list all agents
softcat purr <name>        # status check
softcat feed <name>        # show recent outputs
softcat nap <name>         # pause agent
softcat wake <name>        # resume agent
softcat hiss <name>        # kill agent permanently
softcat groom              # update all agents to latest framework
softcat adopt <template>   # install a community agent template
softcat meow               # interactive chat mode for complex agent design
```

## Configuration

```bash
~/.softcat/
├── config.yaml          # global settings
├── agents/              # spawned agents live here
│   ├── hn-digest/
│   │   ├── agent.py     # generated agent code
│   │   ├── prompt.md    # prompt template
│   │   ├── config.yaml  # agent-specific config
│   │   └── outputs/     # agent outputs
│   └── ...
└── templates/           # community templates
```

## Requirements

- Python 3.10+
- Anthropic API key
- Optional: Healthchecks.io API key (for monitoring)
- Optional: cron or systemd (for scheduling)

## Built by Valori

SOFT CAT is built and maintained by [Valori](https://softcat.ai/valori) — a small collective of AI practitioners. No names. No faces. Just the work.

## License

MIT
