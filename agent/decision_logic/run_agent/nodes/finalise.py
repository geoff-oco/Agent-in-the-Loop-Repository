from graph.state import ChatState
from helpers.finalise_support import FinaliseSupport


def node(state: ChatState) -> ChatState:

    # Check if simple or detailed path
    if getattr(state, "mode", "detail") == "simple":

        # If it is simple it has its own formatting
        state.last_reply = FinaliseSupport.format_simple(state.simple_output or {})
        return state

    # If its detailed we format in that way
    state.last_reply = FinaliseSupport.format(state.runtime or {})
    return state
