from typing import TypedDict, List, Optional, Any

class AgentState(TypedDict):
    query: str
    category: str        # 'indication', 'brand_name', 'generic_name', 'invalid', 'general_medical'
    keyword: str         # Extracted keyword for search
    symptom: Optional[str]
    fda_data: Optional[Any] # Can be dict or list
    dur_data: Optional[List[dict]]
    final_answer: Optional[str]
    user_profile: Optional[dict]
