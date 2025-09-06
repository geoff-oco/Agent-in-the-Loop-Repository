#Imports required for building the graph including our nodes
from langgraph.graph import StateGraph, END
from graph.state import ChatState

#Import all of our nodes here
from nodes.prepare_select import node as node_prepare_and_select
from nodes.advise import node as node_advise
from nodes.finalise import node as node_finalise

def build_graph():
    g = StateGraph(ChatState)

    #This is where we add our nodes
    g.add_node("prepare_and_select", node_prepare_and_select)
    g.add_node("advise", node_advise)
    g.add_node("finalise", node_finalise)

    #This is where we define the flow of the graph and add edges
    g.set_entry_point("prepare_and_select")
    g.add_edge("prepare_and_select", "advise")
    g.add_edge("advise", "finalise")
    g.add_edge("finalise", END)
    return g.compile()
