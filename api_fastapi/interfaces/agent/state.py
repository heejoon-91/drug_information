from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    query: str
    category: Optional[str]
    keyword: Optional[str]
    symptom: Optional[str]
    cache_key: Optional[str]
    is_cached: bool
    fda_data: Optional[any]
    dur_data: Optional[List[dict]]
    ingredients_data: Optional[List[dict]]
    final_answer: Optional[str]
    user_profile: Optional[dict]
