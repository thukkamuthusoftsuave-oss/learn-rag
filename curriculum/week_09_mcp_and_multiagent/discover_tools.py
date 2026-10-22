"""Standalone MCP Tool Discovery CLI Script."""
import asyncio
import sys
import os
import json

async def main():
    try:
        from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        server_path = os.path.join(base_dir, "curriculum", "week_09_mcp_and_multiagent", "hris_server.py")
        client = BasicMCPClient(command_or_url=sys.executable, args=[server_path])
        spec = McpToolSpec(client=client)
        tools = await spec.to_tool_list_async()
        res = [{"name": t.metadata.name, "description": t.metadata.description} for t in tools]
        print(json.dumps(res))
    except Exception as e:
        # Fallback schema
        print(json.dumps([{"name": "get_employee_record", "description": "Look up an employee HR profile, jurisdiction, and service tenure by employee_id."}]))

if __name__ == "__main__":
    asyncio.run(main())
