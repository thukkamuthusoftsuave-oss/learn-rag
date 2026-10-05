# Week 9: MCP, Multi-agent & A2A

## What this week is about
This week focuses on the **Model Context Protocol (MCP)**, an industry standard for connecting AIs to tools and data. Currently, every tool you give an agent is wired in by hand (like our original `create_llama_tools()` implementation). With MCP, we introduce a shared standard ("socket") where tools can be reused by any AI seamlessly.

## Key Concepts
1. **Host, Client, Server**: The *Host* is your application running the AI. The *Client* sits inside your host and speaks MCP. The *Server* exposes tools. The AI *never* runs on the server.
2. **Tools, Resources, Prompts**: MCP allows servers to expose actionable functions (Tools), static data (Resources), and prompt templates.
3. **Transports**: We primarily use the `stdio` transport to communicate between the client and server locally, but `HTTP/SSE` is used for remote MCP communication.
4. **Tool Discovery**: Instead of importing functions directly, the client queries the server for its available tools via a JSON-RPC handshake.

## The Assignment: Track C (HR Policy)
The goal is to bolt on the HRIS server without touching the agent. We do this by spinning up a lightweight `fastmcp` server that serves the `get_employee_record` tool.

### Files Provided:
* `hris_server.py`: A `fastmcp` server exposing the HR-207 Employee Database lookup.
* `agent_mcp_client.py`: An example showing how an agent discovers the tool over MCP instead of hard-coding the logic.

### How to test:
```bash
python agent_mcp_client.py
```
This will start the MCP Server subprocess, discover the tool dynamically, and let a sample ReAct agent use it!
