"""MCP server command for CLI Agent Orchestrator CLI."""

import click


@click.command(name="mcp-server")
def mcp_server():
    """Start the CAO MCP server."""
    # Imported here rather than at module top: the server pulls in fastmcp, several hundred
    # milliseconds of imports that `cao mcp-server --help` and its shell completion don't need.
    from cli_agent_orchestrator.mcp_server.server import main as run_mcp_server

    click.echo("Starting CAO MCP server...")
    run_mcp_server()
