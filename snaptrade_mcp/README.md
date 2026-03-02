# SnapTrade MCP Server

A read-only MCP (Model Context Protocol) server that connects AI agents to brokerage data via SnapTrade. Works with Claude Code, Claude Desktop, Cursor, Windsurf, and any MCP-compatible client.

**10 tools. Read-only. No trading. Safe by design.**

## What You Can Do

| Tool | Description |
|------|-------------|
| `snaptrade_list_accounts` | List all connected brokerage accounts |
| `snaptrade_get_balance` | Cash balances for an account |
| `snaptrade_get_positions` | Current holdings (stocks, ETFs) |
| `snaptrade_get_orders` | Order history with filters |
| `snaptrade_get_activities` | Transaction log (dividends, fees) |
| `snaptrade_portfolio_summary` | All accounts + balances + positions in one call |
| `snaptrade_search_symbols` | Look up stocks/ETFs by name or ticker |
| `snaptrade_list_brokerages` | Supported brokerages |
| `snaptrade_check_status` | API health check |
| `snaptrade_setup` | Generate URL to connect a new brokerage |

## Prerequisites

1. **SnapTrade API credentials** — a `clientId` and `consumerKey` from [snaptrade.com](https://snaptrade.com). Sign up for a developer account and find your keys in the dashboard.
2. **Python 3.10+**

## Where do my API keys go?

Your SnapTrade credentials never leave your machine. Here's what happens:

- Your `clientId` and `consumerKey` are stored in a **local config file** on your computer (or in environment variables you set yourself).
- The MCP server reads them at startup to authenticate with SnapTrade's API.
- They are **never** sent to your AI client, **never** included in tool responses, and **never** logged.
- The server is read-only — it cannot trade, modify accounts, or delete anything.

This is the same way any API integration handles credentials. Your keys stay on your machine, period.

## Installation

### Option A: Install from PyPI (recommended)

```bash
pip install snaptrade-mcp
```

That's it. This installs the `snaptrade-mcp` command and all dependencies.

### Option B: Install from source

```bash
git clone https://github.com/micah63/snaptrade-mcp-server.git
cd snaptrade-mcp-server
pip install .
```

## Add the MCP server to your AI client

### Claude Code

The `-s user` flag stores your credentials in your personal Claude config (`~/.claude/`), not in the project — so they never end up in git.

```bash
claude mcp add snaptrade -s user \
  -e SNAPTRADE_CLIENT_ID=your_client_id \
  -e SNAPTRADE_CONSUMER_KEY=your_consumer_key \
  -- snaptrade-mcp
```

Then restart Claude Code and run `/mcp` to verify the server appears with all 10 tools.

**Alternative:** If you prefer to set credentials as environment variables in your shell (add to `~/.zshrc` or `~/.bashrc`), you can skip the `-e` flags:

```bash
# In your ~/.zshrc or ~/.bashrc:
export SNAPTRADE_CLIENT_ID="your_client_id"
export SNAPTRADE_CONSUMER_KEY="your_consumer_key"

# Then register without -e flags:
claude mcp add snaptrade -s user -- snaptrade-mcp
```

### Claude Desktop

Add to your `claude_desktop_config.json` (Settings > Developer > Edit Config). This file lives in your user directory and is not part of any project.

```json
{
  "mcpServers": {
    "snaptrade": {
      "command": "snaptrade-mcp",
      "env": {
        "SNAPTRADE_CLIENT_ID": "your_client_id",
        "SNAPTRADE_CONSUMER_KEY": "your_consumer_key"
      }
    }
  }
}
```

Restart Claude Desktop. The SnapTrade tools will appear in the tools menu.

### Cursor

Add to `.cursor/mcp.json` in your project root. **Add `.cursor/mcp.json` to your `.gitignore`** so credentials don't get committed.

```json
{
  "mcpServers": {
    "snaptrade": {
      "command": "snaptrade-mcp",
      "env": {
        "SNAPTRADE_CLIENT_ID": "your_client_id",
        "SNAPTRADE_CONSUMER_KEY": "your_consumer_key"
      }
    }
  }
}
```

## First-Time Setup

After installing, ask your AI agent:

> "Set up my SnapTrade connection"

This calls `snaptrade_setup`, which opens a browser window where you authorize your brokerage. You only need to do this once. Your user credentials are saved locally at `~/.snaptrade/config.json`.

## Example Prompts

- "What brokerage accounts do I have?"
- "Show me my full portfolio summary"
- "What's my cash balance across all accounts?"
- "Analyze my portfolio for diversification risk"
- "What trades have I made recently?"
- "Search for Apple stock"
- "Which brokerages does SnapTrade support?"

## Troubleshooting

**Server fails to connect / "Failed to reconnect"**
- Verify the package is installed: `python -c "from snaptrade_mcp.server import main; print('OK')"`
- If using a virtual environment, make sure `snaptrade-mcp` is installed in that environment.

**"Missing credentials" error**
- Check that `SNAPTRADE_CLIENT_ID` and `SNAPTRADE_CONSUMER_KEY` are set in the `-e` flags (Claude Code) or `env` block (Claude Desktop / Cursor).

**"No config found" error**
- Run `snaptrade_setup` through the MCP server first to connect a brokerage and create `~/.snaptrade/config.json`.

## Security

- **Read-only** — no trading, no account modification, no deletes
- **Credentials isolated** — API keys loaded from env vars, user secrets stored at `~/.snaptrade/config.json` (chmod 600). Neither appears in tool responses.
- **No dangerous operations** — cannot delete users, reset secrets, or modify anything

## Architecture

```
snaptrade_mcp/
  server.py         # All 10 tools, 2 resources, 2 prompt templates
  __init__.py       # Package marker + version
  __main__.py       # Entry point (python -m snaptrade_mcp)
  requirements.txt  # Dependencies
  README.md         # This file
```

The server runs over STDIO (the default MCP transport). Each tool function calls the SnapTrade Python SDK, flattens the response into clean JSON, and returns it to the AI agent.
