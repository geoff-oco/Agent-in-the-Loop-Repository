import json
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage # AIMessage, HumanMessage, SystemMessage used for LLM interaction
from helpers.helpers import Helpers
from helpers.readers import Readers

def node(state):
    llm = Helpers.get_langchain_llm(state.base_url, state.model) # Get the LLM instance

    #concatenate our various markdown prompts for our message again
    sys_txt = Readers.read_prompt(state.prompts_dir, "system.md") 
    glob_txt = Readers.read_prompt(state.prompts_dir, "global_context.md")
    inst = Readers.read_prompt(state.prompts_dir, "ReadingJSON.md") #This one severely improved results by telling the LLM how to interpret the JSON return
    adv_txt = Readers.read_prompt(state.prompts_dir, "advise_instructions.md")
    game_json = json.dumps(state.game_state, ensure_ascii=False)
    sel_blob = "\n".join([f"### {k}\n{v}" for k, v in state.selected_texts.items()]) if state.selected_texts else ""
    body = "\n\n".join([t for t in [glob_txt, inst, game_json, adv_txt, sel_blob] if t])

    # Build the message list for the LLM
    msgs = []
    if sys_txt:
        msgs.append(SystemMessage(content=sys_txt))
    msgs.append(HumanMessage(content=body))

    Helpers.log("sending request for new strategy to LLM...")

    # aaand send it!
    ai: AIMessage = llm.invoke(msgs)

    # LOG what the LLM replied
    reply_text = ai.content if isinstance(ai.content, str) else str(ai.content)
    Helpers.log("Received new strategy from LLM")

    #finalise state
    state.last_reply = reply_text if isinstance(reply_text, str) and reply_text.strip() else "No advice available."
    state.messages = (state.messages or []) + msgs + [ai]
    return state
