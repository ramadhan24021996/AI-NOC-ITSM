"""
Shim module re-exporting KnowledgeAutoBuilder from python_ai_core.knowledge.knowledge_auto_builder.
"""
try:
    from python_ai_core.knowledge.knowledge_auto_builder import KnowledgeAutoBuilder
except ImportError:
    from SERVER.python_ai_core.knowledge.knowledge_auto_builder import KnowledgeAutoBuilder

__all__ = ["KnowledgeAutoBuilder"]
