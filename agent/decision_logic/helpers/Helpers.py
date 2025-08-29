import base64, requests #base64 is the only image type Ollama accepts.
from typing import List, Dict, Any

class Helpers:
    #Helpers - simple helper methods to be used by our nodes
    @staticmethod
    def _file_to_b64(path: str) -> str:
        #This is used to read an image we pass and convert to base64
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @staticmethod
    def _ollama_chat(base_url: str, model: str, system: str, messages: List[Dict[str, Any]]) -> str:
        #This is the payload, the actual request to the LLM, its built from our current state
        payload = { #The payload is the actual chat request sent to Ollama. Needs a model, role and content
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,  # prepend system message
            "stream": False,  # rather than stream we are asking for the entire reply.
        }
        r = requests.post(f"{base_url}/api/chat", json=payload, timeout=300)  # send POST to Ollama API
        if not r.ok:  # if the response code isn’t 200
            raise RuntimeError(f"Ollama error {r.status_code}: {r.text}")  # show server error
        return r.json().get("message", {}).get("content", "")  # return just the text reply





