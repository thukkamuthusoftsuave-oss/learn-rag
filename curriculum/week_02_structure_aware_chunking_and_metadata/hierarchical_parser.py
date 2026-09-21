"""Week 2: Hierarchical (Parent-Child) Node Parser.

Demonstrates using LlamaIndex's HierarchicalNodeParser to create
small leaf nodes for precision retrieval and large parent nodes for context-rich generation.
"""

from typing import List
from llama_index.core.schema import Document, BaseNode
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes


def create_hierarchical_nodes(documents: List[Document], chunk_sizes: List[int] = None) -> tuple[List[BaseNode], List[BaseNode]]:
    """Generates a hierarchical multi-tier node structure.
    
    Args:
        documents: List of LlamaIndex Document instances with metadata.
        chunk_sizes: Sizes for hierarchy levels, e.g. [512, 128].
        
    Returns:
        (all_nodes, leaf_nodes)
    """
    if chunk_sizes is None:
        chunk_sizes = [512, 128]
        
    node_parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=chunk_sizes,
        chunk_overlap=20
    )
    
    all_nodes = node_parser.get_nodes_from_documents(documents)
    leaf_nodes = get_leaf_nodes(all_nodes)
    
    return all_nodes, leaf_nodes
