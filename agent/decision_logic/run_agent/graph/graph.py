from langgraph.graph import StateGraph, END
from graph.state import ChatState

# Import all of our nodes
from nodes.prepare_select import node as node_prepare_and_select
from nodes.summary import node as node_summary
from nodes.phase_step import node as node_phase_step
from nodes.rationale import node as node_rationale
from nodes.finalise import node as node_finalise
from nodes.simple_advice import node as node_simple_advice


# ----------------------CONDITIONAL EDGES----------------------#
# Grabs the state and checks if the mode is simple or detail for routing
def _route_after_prepare(state: ChatState):
    return "simple" if getattr(state, "mode", "detail") == "simple" else "detail"


# Loops through the phases until phase 3 then routes to rationale
def _loop_router(state: ChatState):
    return "phase" if state.current_phase <= 3 else "rationale"


# ----------------------BUILD GRAPH----------------------#
def build_graph():
    g = StateGraph(ChatState)
    g.add_node("prepare_and_select", node_prepare_and_select)
    g.add_node("simple_advice", node_simple_advice)
    g.add_node("summary", node_summary)
    g.add_node("phase", node_phase_step)
    g.add_node("rationale", node_rationale)
    g.add_node("finalise", node_finalise)

    # Set our edges
    g.set_entry_point("prepare_and_select")
    g.add_conditional_edges(
        "prepare_and_select", _route_after_prepare, {"simple": "simple_advice", "detail": "summary"}
    )
    g.add_edge("summary", "phase")
    g.add_conditional_edges("phase", _loop_router, {"phase": "phase", "rationale": "rationale"})
    g.add_edge("rationale", "finalise")
    g.add_edge("simple_advice", "finalise")
    g.add_edge("finalise", END)
    return g
