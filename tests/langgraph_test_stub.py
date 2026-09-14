"""Minimal test-only graph runner for hosts without the required LangGraph wheel.

This is never imported by application code. It lets deterministic node behavior
be tested in constrained workspaces while the real framework integration remains
an explicit deployment/runtime gate.
"""

from __future__ import annotations

import inspect
import sys
import types
from collections.abc import Callable


def install() -> None:
    if "langgraph.graph" in sys.modules:
        return

    graph_module = types.ModuleType("langgraph.graph")
    graph_module.END = "__END__"

    class StateGraph:
        def __init__(self, _state_type):
            self.nodes: dict[str, Callable] = {}
            self.entry: str | None = None
            self.edges: dict[str, str] = {}
            self.conditional: dict[str, tuple[Callable, dict[str, str]]] = {}

        def add_node(self, name: str, node: Callable) -> None:
            self.nodes[name] = node

        def set_entry_point(self, name: str) -> None:
            self.entry = name

        def add_edge(self, source: str, target: str) -> None:
            self.edges[source] = target

        def add_conditional_edges(
            self, source: str, chooser: Callable, mapping: dict[str, str]
        ) -> None:
            self.conditional[source] = (chooser, mapping)

        def compile(self):
            nodes = self.nodes
            entry = self.entry
            edges = self.edges
            conditional = self.conditional

            class CompiledGraph:
                async def ainvoke(self, initial_state: dict) -> dict:
                    state = dict(initial_state)
                    current = entry
                    while current != graph_module.END:
                        result = nodes[current](state)
                        if inspect.isawaitable(result):
                            result = await result
                        state.update(result or {})
                        if current in conditional:
                            chooser, mapping = conditional[current]
                            current = mapping[chooser(state)]
                        else:
                            current = edges[current]
                    return state

            return CompiledGraph()

    graph_module.StateGraph = StateGraph
    package = types.ModuleType("langgraph")
    package.graph = graph_module
    sys.modules["langgraph"] = package
    sys.modules["langgraph.graph"] = graph_module
