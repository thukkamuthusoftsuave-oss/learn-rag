"""Example showing how an Agent connects to a tool via MCP.
This replaces the hard-coded "create_llama_tools" for learning purposes.
"""
import os
import sys
import asyncio
from llama_index.core.agent import ReActAgent
from llama_index.core.llms import ChatMessage, ChatResponse
from llama_index.core.llms.custom import CustomLLM
from llama_index.core.tools import FunctionTool

# Optional MCP imports
try:
    from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
except ImportError:
    BasicMCPClient = None
    McpToolSpec = None

# A dummy LLM for demonstration purposes that just calls the tool once
class DummyLLM(CustomLLM):
    employee_id: str = "EMP-102"
    step: int = 0
    
    @property
    def metadata(self):
        from llama_index.core.llms import LLMMetadata
        return LLMMetadata(context_window=4096, num_output=512, is_chat_model=True, model_name="dummy")

    def chat(self, messages, **kwargs) -> ChatResponse:
        self.step += 1
        if self.step == 1:
            content = f"Thought: I need to query the employee record.\nAction: get_employee_record\nAction Input: {{\"employee_id\": \"{self.employee_id}\"}}"
            return ChatResponse(message=ChatMessage(role="assistant", content=content))
        
        content = "Thought: I got the employee details.\nAnswer: The lookup is complete."
        return ChatResponse(message=ChatMessage(role="assistant", content=content))
        
    def complete(self, prompt: str, **kwargs):
        pass
    
    def stream_complete(self, prompt: str, **kwargs):
        pass

async def main():
    if not BasicMCPClient:
        print("llama-index-tools-mcp is not installed. Please install it to run this example.")
        return

    print("Connecting to the MCP Server...")
    server_path = os.path.join(os.path.dirname(__file__), "hris_server.py")
    
    # We use BasicMCPClient to connect to the fastmcp server script via stdio transport
    client = BasicMCPClient(command_or_url=sys.executable, args=[server_path])
    mcp_tool_spec = McpToolSpec(client=client)
    
    # Dynamically fetch the tools from the server!
    tools = await mcp_tool_spec.to_tool_list_async()
    
    print(f"Discovered {len(tools)} tools over MCP:")
    for t in tools:
        print(f" - {t.metadata.name}: {t.metadata.description}")

    print("\nStarting ReAct Agent with the discovered MCP tool...")
    agent = ReActAgent.from_tools(
        tools=tools,
        llm=DummyLLM(),
        verbose=True
    )
    
    response = await agent.achat("What is the profile for EMP-102?")
    print(f"\nFinal Agent Response: {response.response}")

if __name__ == "__main__":
    asyncio.run(main())
