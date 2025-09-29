from typing import Dict

class PhaseMath:

    #Sums all units across L,H and R. we can use it to tell if bases are empty, compute budgets etc
    @staticmethod
    def sum_counts(s: Dict[str, int]) -> int:
        return int(s.get("L", 0)) + int(s.get("H", 0)) + int(s.get("R", 0))

    #Creates a vector dictionary we can further use for budgets or deciding when to clamp
    @staticmethod
    def vec(L=0, H=0, R=0) -> Dict[str, int]:
        return {"L": int(L), "H": int(H), "R": int(R)}

    #Adds 1 dictionary of units the vector to another returning a mutated dictionary for inserts, movements to bases etc
    @staticmethod
    def add(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]:
        return {"L": a.get("L", 0) + b.get("L", 0),
                "H": a.get("H", 0) + b.get("H", 0),
                "R": a.get("R", 0) + b.get("R", 0)}

    #Subtracts one vector from another, such as moving from a base, inserts and the like
    @staticmethod
    def sub(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]:
        return {"L": a.get("L", 0) - b.get("L", 0),
                "H": a.get("H", 0) - b.get("H", 0),
                "R": a.get("R", 0) - b.get("R", 0)}

    # To assert equal between 2 vectors, it will tell us if there was any change from say the original.
    @staticmethod
    def eq(a: Dict[str, int], b: Dict[str, int]) -> bool:
        return int(a.get("L",0))==int(b.get("L",0)) and int(a.get("H",0))==int(b.get("H",0)) and int(a.get("R",0))==int(b.get("R",0))

    #Resets a negative count, like we get from the LLM, to 0
    @staticmethod
    def clamp_nonneg(v: Dict[str, int]) -> Dict[str, int]:
        return {"L": max(0, v.get("L", 0)),
                "H": max(0, v.get("H", 0)),
                "R": max(0, v.get("R", 0))}
