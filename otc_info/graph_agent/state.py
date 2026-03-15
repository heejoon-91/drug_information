from typing import TypedDict, List, Optional, Any, Dict


class AgentState(TypedDict, total=False):
    query: str
    category: str
    keyword: str
    symptom: Optional[str]
    symptom_term: Optional[str]
    symptom_context: Optional[str]
    symptom_followup: Optional[Dict[str, Any]]
    fda_data: Optional[Dict[str, Any]]
    dur_data: Optional[List[dict]]
    final_answer: Optional[str]
    user_profile: Optional[dict]
    user_info: Optional[dict]
    ingredients_data: Optional[List[dict]]
    cache_key: Optional[str]
    is_cached: Optional[bool]
    cache_source: Optional[str]
