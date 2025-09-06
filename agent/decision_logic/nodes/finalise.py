from langchain_core.messages import AIMessage

#smallest node, just finalises the state with the last reply from the LLM or a default message if none
def node(state):
    final = state.last_reply or "No advice available."
    state.last_reply = final
    state.messages = [AIMessage(content=final)]
    return state

