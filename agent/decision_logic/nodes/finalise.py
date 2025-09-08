from langchain_core.messages import AIMessage
from helpers.helpers import Helpers

#smallest node, just finalises the state with the last reply from the LLM or a default message if none
def node(state):
    Helpers.log("Finalising state with last reply...")
    final = state.last_reply or "No advice available."
    state.last_reply = final
    state.messages = [AIMessage(content=final)]
    Helpers.log("State finalised.")
    return state

