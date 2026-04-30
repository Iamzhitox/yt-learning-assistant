from langgraph.types import Command
from src.application.graph.state import State
from src.application.agents.teacher_agent import get_teacher_agent


def teacher_node(state: State) -> Command:
    agent = get_teacher_agent()
    messages = state.get("messages", [])
    instruction = [messages[-1]] if messages else []
    result = agent.invoke({"messages": instruction})

    last_message = result["messages"][-1]

    return Command(
        goto="agent_manager",
        update={"agent_output": last_message.content},
    )
