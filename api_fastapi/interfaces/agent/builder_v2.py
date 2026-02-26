from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes_v2 import (
    classify_node,
    retrieve_fda_node,
    retrieve_dur_node,
    generate_symptom_answer_node,
    generate_product_answer_node,
    generate_general_answer_node,
    generate_error_node
)

def build_graph():
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("classify", classify_node)
    workflow.add_node("retrieve_fda", retrieve_fda_node)
    workflow.add_node("retrieve_dur", retrieve_dur_node)
    workflow.add_node("generate_symptom_answer", generate_symptom_answer_node)
    workflow.add_node("generate_product_answer", generate_product_answer_node)
    workflow.add_node("generate_general_answer", generate_general_answer_node)
    workflow.add_node("generate_error", generate_error_node)

    # 엣지 및 조건부 로직 설정
    workflow.set_entry_point("classify")

    def route_after_classify(state: AgentState):
        category = state["category"]
        if category == "symptom_recommendation":
            return "recommend"
        elif category == "product_request":
            return "product"
        elif category == "general_medical":
            return "general"
        else:
            return "error"

    workflow.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "recommend": "retrieve_fda",
            "product": "retrieve_fda",
            "general": "generate_general_answer",
            "error": "generate_error"
        }
    )

    def route_after_fda(state: AgentState):
        category = state["category"]
        if category == "symptom_recommendation":
            return "dur"
        else:
            return "dur"

    workflow.add_edge("retrieve_fda", "retrieve_dur")

    def route_after_dur(state: AgentState):
        category = state["category"]
        if category == "symptom_recommendation":
            return "symptom_ans"
        else:
            return "product_ans"

    workflow.add_conditional_edges(
        "retrieve_dur",
        route_after_dur,
        {
            "symptom_ans": "generate_symptom_answer",
            "product_ans": "generate_product_answer"
        }
    )

    workflow.add_edge("generate_symptom_answer", END)
    workflow.add_edge("generate_product_answer", END)
    workflow.add_edge("generate_general_answer", END)
    workflow.add_edge("generate_error", END)

    return workflow.compile()
