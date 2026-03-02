"""
SnapTrade MCP Server — read-only brokerage data for AI agents.

Exposes 10 tools, 2 resources, and 2 prompt templates via the Model Context
Protocol. Works with Claude Code, Claude Desktop, Cursor, Windsurf, and any
other MCP-compatible client.

All tools are read-only. No trading, no account modification, no credential
exposure. Safe by design.
"""

import json
import os
import webbrowser
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from snaptrade_client import SnapTrade

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "snaptrade",
    instructions="Read-only access to brokerage accounts via SnapTrade. "
    "View balances, positions, orders, and transactions across any connected brokerage.",
)

CONFIG_PATH = Path.home() / ".snaptrade" / "config.json"


def _get_client():
    """Initialize SnapTrade client from environment variables."""
    client_id = os.environ.get("SNAPTRADE_CLIENT_ID")
    consumer_key = os.environ.get("SNAPTRADE_CONSUMER_KEY")

    if not client_id or not consumer_key:
        raise ValueError(
            "Missing credentials. Set SNAPTRADE_CLIENT_ID and "
            "SNAPTRADE_CONSUMER_KEY environment variables."
        )

    return SnapTrade(consumer_key=consumer_key, client_id=client_id), client_id


def _get_user():
    """Load user credentials from local config."""
    if not CONFIG_PATH.exists():
        raise ValueError(
            f"No config found at {CONFIG_PATH}. "
            "Run the snaptrade_setup tool first to connect a brokerage."
        )

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    user_id = config.get("user_id")
    user_secret = config.get("user_secret")

    if not user_id or not user_secret:
        raise ValueError(
            "Config is missing user_id or user_secret. "
            "Run the snaptrade_setup tool to re-connect."
        )

    return user_id, user_secret


def _serialize(obj):
    """Convert SDK response objects to clean JSON-serializable dicts."""
    if hasattr(obj, "body"):
        obj = obj.body
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return obj


def _format_response(data):
    """Return a clean JSON string for the AI to consume."""
    return json.dumps(_serialize(data), indent=2, default=str)


def _clean_error(e):
    """Extract a concise error message from SDK exceptions."""
    msg = str(e)
    # SDK exceptions include full HTTP response — extract just the body
    if "HTTP response body:" in msg:
        try:
            body_str = msg.split("HTTP response body:")[1].strip()
            import ast
            body = ast.literal_eval(body_str)
            detail = body.get("detail", body_str)
            code = body.get("code", "")
            return f"{detail} (code: {code})" if code else detail
        except Exception:
            pass
    # Fallback: first line only
    return msg.split("\n")[0]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def snaptrade_list_accounts() -> str:
    """List all connected brokerage accounts.

    Returns account IDs, names, institution names, and account types.
    This is usually the first tool to call — it discovers what's available.
    """
    client, _ = _get_client()
    user_id, user_secret = _get_user()

    response = client.account_information.list_user_accounts(
        user_id=user_id, user_secret=user_secret,
    )
    accounts = _serialize(response)

    if not accounts:
        return json.dumps({
            "accounts": [],
            "message": "No accounts found. Use snaptrade_setup to connect a brokerage.",
        })

    return _format_response({"accounts": accounts, "count": len(accounts)})


@mcp.tool()
def snaptrade_get_balance(account_id: str) -> str:
    """Get cash balances for a specific brokerage account.

    Args:
        account_id: The account ID (get this from snaptrade_list_accounts).

    Returns cash balances with currency information.
    """
    client, _ = _get_client()
    user_id, user_secret = _get_user()

    response = client.account_information.get_user_account_balance(
        account_id=account_id, user_id=user_id, user_secret=user_secret,
    )
    return _format_response({"account_id": account_id, "balances": _serialize(response)})


@mcp.tool()
def snaptrade_get_positions(account_id: str) -> str:
    """Get current holdings (stocks, ETFs, etc.) for a specific account.

    Args:
        account_id: The account ID (get this from snaptrade_list_accounts).

    Returns positions with symbol, quantity, market value, and price info.
    """
    client, _ = _get_client()
    user_id, user_secret = _get_user()

    response = client.account_information.get_user_account_positions(
        account_id=account_id, user_id=user_id, user_secret=user_secret,
    )
    return _format_response({"account_id": account_id, "positions": _serialize(response)})


@mcp.tool()
def snaptrade_get_orders(account_id: str, status: str = "all") -> str:
    """Get order history for a specific account.

    Args:
        account_id: The account ID (get this from snaptrade_list_accounts).
        status: Filter by order status — "all", "open", "executed", or "cancelled".

    Returns orders with date, symbol, action, quantity, price, and status.
    """
    client, _ = _get_client()
    user_id, user_secret = _get_user()

    kwargs = dict(
        account_id=account_id, user_id=user_id, user_secret=user_secret,
    )
    if status != "all":
        kwargs["status"] = status

    response = client.account_information.get_user_account_orders(**kwargs)
    return _format_response({"account_id": account_id, "status_filter": status, "orders": _serialize(response)})


@mcp.tool()
def snaptrade_get_activities(account_id: str) -> str:
    """Get transaction history (dividends, fees, transfers) for an account.

    Args:
        account_id: The account ID (get this from snaptrade_list_accounts).

    Returns activities like dividends received, fees charged, deposits, etc.
    """
    client, _ = _get_client()
    user_id, user_secret = _get_user()

    response = client.transactions_and_reporting.get_activities(
        user_id=user_id, user_secret=user_secret, account_id=account_id,
    )
    return _format_response({"account_id": account_id, "activities": _serialize(response)})


@mcp.tool()
def snaptrade_portfolio_summary() -> str:
    """Get a complete portfolio overview — all accounts with balances and positions.

    This is the showpiece tool. It combines account info, cash balances, and
    current holdings into a single response. Use this when the user asks for
    a full picture of their investments.
    """
    client, _ = _get_client()
    user_id, user_secret = _get_user()

    response = client.account_information.list_user_accounts(
        user_id=user_id, user_secret=user_secret,
    )
    accounts = _serialize(response)

    if not accounts:
        return json.dumps({
            "portfolio": [],
            "message": "No accounts found. Use snaptrade_setup to connect a brokerage.",
        })

    portfolio = []
    for acct in accounts:
        acct_id = acct.get("id") or acct.get("brokerage_account_id")
        entry = {
            "account_name": acct.get("name", acct_id),
            "account_id": acct_id,
            "institution": acct.get("institution_name", "Unknown"),
            "type": acct.get("type") or acct.get("account_type", "Unknown"),
        }

        try:
            bal = client.account_information.get_user_account_balance(
                account_id=acct_id, user_id=user_id, user_secret=user_secret,
            )
            entry["balances"] = _serialize(bal)
        except Exception as e:
            entry["balances"] = {"error": _clean_error(e)}

        try:
            pos = client.account_information.get_user_account_positions(
                account_id=acct_id, user_id=user_id, user_secret=user_secret,
            )
            entry["positions"] = _serialize(pos)
        except Exception as e:
            entry["positions"] = {"error": _clean_error(e)}

        portfolio.append(entry)

    return _format_response({"portfolio": portfolio, "account_count": len(portfolio)})


@mcp.tool()
def snaptrade_search_symbols(query: str) -> str:
    """Search for stocks, ETFs, or other securities by name or ticker symbol.

    Args:
        query: A company name or ticker symbol (e.g. "Apple" or "AAPL").

    Returns matching symbols with exchange and security type info.
    """
    client, _ = _get_client()
    user_id, user_secret = _get_user()

    response = client.reference_data.symbol_search_user_account(
        user_id=user_id, user_secret=user_secret,
        body={"substring": query},
    )
    return _format_response({"query": query, "results": _serialize(response)})


@mcp.tool()
def snaptrade_list_brokerages() -> str:
    """List all brokerages supported by SnapTrade.

    Returns brokerage names, logos, supported features, and connection status.
    Useful for answering "which brokerages can I connect?" or helping a user
    pick which brokerage to link.
    """
    client, _ = _get_client()

    response = client.reference_data.list_all_brokerages()
    brokerages = _serialize(response)

    summary = []
    for b in brokerages:
        summary.append({
            "name": b.get("name", "Unknown"),
            "id": b.get("id"),
            "status": b.get("status"),
            "type": b.get("brokerage_type") or b.get("type"),
        })

    return _format_response({"brokerages": summary, "count": len(summary)})


@mcp.tool()
def snaptrade_check_status() -> str:
    """Check if the SnapTrade API is reachable and credentials are valid.

    Tests the connection, verifies credentials, and confirms whether the user
    has any linked accounts. Use this for diagnostics when something isn't working.
    """
    result = {"api": "unknown", "credentials": "unknown", "user": "unknown", "accounts": 0}

    try:
        client, client_id = _get_client()
        result["credentials"] = "valid"
    except Exception as e:
        result["credentials"] = f"error: {e}"
        return _format_response(result)

    try:
        user_id, user_secret = _get_user()
        result["user"] = "configured"
    except Exception as e:
        result["user"] = f"error: {e}"
        return _format_response(result)

    try:
        response = client.account_information.list_user_accounts(
            user_id=user_id, user_secret=user_secret,
        )
        accounts = _serialize(response)
        result["api"] = "connected"
        result["accounts"] = len(accounts)
    except Exception as e:
        result["api"] = f"error: {_clean_error(e)}"

    return _format_response(result)


@mcp.tool()
def snaptrade_setup() -> str:
    """Generate a URL to connect a new brokerage account via SnapTrade.

    This creates a secure connection portal where the user can authorize
    access to their brokerage. The URL opens in their browser.

    Only needed once per brokerage. After connecting, all other tools will
    have access to the account data.
    """
    client, client_id = _get_client()

    # Load or create user
    config_dir = CONFIG_PATH.parent
    config_dir.mkdir(parents=True, exist_ok=True)

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        user_id = config.get("user_id")
        user_secret = config.get("user_secret")
    else:
        user_id = None
        user_secret = None

    # Register user if needed
    if not user_id or not user_secret:
        import uuid
        new_user_id = f"mcp-{uuid.uuid4().hex[:12]}"
        reg = client.authentication.register_snap_trade_user(
            body={"userId": new_user_id},
        )
        reg_data = _serialize(reg)
        user_id = reg_data.get("userId", new_user_id)
        user_secret = reg_data.get("userSecret")

        config = {"user_id": user_id, "user_secret": user_secret}
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        CONFIG_PATH.chmod(0o600)

    # Generate connection portal URL
    login = client.authentication.login_snap_trade_user(
        user_id=user_id, user_secret=user_secret,
    )
    login_data = _serialize(login)
    redirect_url = login_data.get("redirectURI") or login_data.get("loginRedirectURI")

    if redirect_url:
        webbrowser.open(redirect_url)
        return json.dumps({
            "status": "opened",
            "message": "A browser window has opened. Please log in to your brokerage "
                       "and authorize the connection. Come back here when done.",
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": "Could not generate a connection URL. Check your SnapTrade credentials.",
    }, indent=2)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("snaptrade://status")
def resource_status() -> str:
    """Current SnapTrade API connection status."""
    return snaptrade_check_status()


@mcp.resource("snaptrade://brokerages")
def resource_brokerages() -> str:
    """List of all supported brokerages."""
    return snaptrade_list_brokerages()


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------


@mcp.prompt()
def analyze_portfolio() -> str:
    """Analyze the user's investment portfolio for diversification, risk, and opportunities."""
    return (
        "Please analyze my investment portfolio. Use snaptrade_portfolio_summary to get "
        "all my account data, then provide:\n\n"
        "1. **Asset allocation** — breakdown by sector, asset type, geography\n"
        "2. **Concentration risk** — any single position >10% of total value?\n"
        "3. **Cash position** — am I holding too much or too little cash?\n"
        "4. **Diversification score** — how well-diversified am I?\n"
        "5. **Observations** — anything notable about my holdings?\n\n"
        "Present the data in clean tables. Be specific with numbers."
    )


@mcp.prompt()
def account_summary() -> str:
    """Get a concise summary of all brokerage accounts."""
    return (
        "Give me a quick summary of all my brokerage accounts. Use "
        "snaptrade_portfolio_summary and present:\n\n"
        "- Each account name and institution\n"
        "- Cash balance per account\n"
        "- Number of positions and total market value\n"
        "- Grand total across all accounts\n\n"
        "Keep it concise — a table is ideal."
    )


def main():
    """Entry point for the snaptrade-mcp console script."""
    mcp.run()


if __name__ == "__main__":
    main()
