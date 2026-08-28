"""启动 MCP stdio 服务端：python -m mcp_server"""
from __future__ import annotations

from mcp_server.server import mcp


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
