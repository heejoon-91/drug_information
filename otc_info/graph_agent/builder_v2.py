from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes_v2 import (
    classify_node,
    retrieve_data_node,
    retrieve_fda_products_node,
    retrieve_dur_node,
    generate_symptom_answer_node,
    generate_product_answer_node,
    generate_general_answer_node,
    generate_error_node,
)


def build_graph():
    """Build the reduced-risk workflow.

    Symptom flow:
        classify -> retrieve_data -> retrieve_dur(no-op) -> answer_symptom

    Product/ingredient flow:
        classify -> retrieve_data(product/ingredient resolve) -> retrieve_dur -> answer_product
    """

    workflow = StateGraph(AgentState)

    workflow.add_node("classify", classify_node)
    workflow.add_node("retrieve_data", retrieve_data_node)
    workflow.add_node("retrieve_fda_products", retrieve_fda_products_node)
    workflow.add_node("retrieve_dur", retrieve_dur_node)
    workflow.add_node("answer_symptom", generate_symptom_answer_node)
    workflow.add_node("answer_product", generate_product_answer_node)
    workflow.add_node("answer_general", generate_general_answer_node)
    workflow.add_node("answer_error", generate_error_node)

    workflow.set_entry_point("classify")

    def route_query(state: AgentState):
        category = state.get("category")
        if category == "symptom_recommendation":
            return "symptom"
        if category == "product_request":
            return "product"
        if category == "general_medical":
            return "general"
        return "error"

    workflow.add_conditional_edges(
        "classify",
        route_query,
        {
            "symptom": "retrieve_data",
            "product": "retrieve_data",
            "general": "answer_general",
            "error": "answer_error",
        },
    )

    def route_after_retrieve_data(state: AgentState):
        category = state.get("category")
        if category == "symptom_recommendation":
            return "symptom"
        if category == "product_request":
            return "product"
        return "error"

    workflow.add_conditional_edges(
        "retrieve_data",
        route_after_retrieve_data,
        {
            "symptom": "retrieve_dur",
            "product": "retrieve_dur",
            "error": "answer_error",
        },
    )

    def route_after_retrieve_dur(state: AgentState):
        category = state.get("category")
        if category == "symptom_recommendation":
            return "answer_symptom"
        if category == "product_request":
            return "answer_product"
        return "answer_error"

    workflow.add_conditional_edges(
        "retrieve_dur",
        route_after_retrieve_dur,
        {
            "answer_symptom": "answer_symptom",
            "answer_product": "answer_product",
            "answer_error": "answer_error",
        },
    )

    workflow.add_edge("answer_symptom", END)
    workflow.add_edge("answer_product", END)
    workflow.add_edge("answer_general", END)
    workflow.add_edge("answer_error", END)
    return workflow.compile()
