"""과제 필수 두 노드: retrieve → generate."""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from services.llm import answer_with_usage
from services.vector_store import retrieve_vectors


class State(TypedDict, total=False):
    item: dict
    question: str
    history: list
    sources: list
    result: dict
    search_mode: str


def retrieve(state):
    return {'sources': retrieve_vectors(state['item'], state['question'], mode=state.get('search_mode', 'similarity'))}


def generate(state):
    result = answer_with_usage(state['item'], state['question'], state['sources'], state['history'])
    return {'result': result, 'sources': result.get('sources', state['sources'])}


builder = StateGraph(State)
builder.add_node('retrieve', retrieve)
builder.add_node('generate', generate)
builder.add_edge(START, 'retrieve')
builder.add_edge('retrieve', 'generate')
builder.add_edge('generate', END)
graph = builder.compile()
