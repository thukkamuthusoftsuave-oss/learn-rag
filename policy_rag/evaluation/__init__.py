"""Offline evaluation suites.

Submodules are imported on demand rather than here, so a command that only
needs one suite does not pay for the others' dependencies (the chunking
bake-off pulls in scikit-learn; the retrieval benchmark loads the embedding
model).

- ``datasets``  - the golden question sets every suite scores against
- ``retrieval`` - vector-only vs hybrid: hit-rate@1/@3 and MRR
- ``chunking``  - naive vs structure-aware chunking: hit-in-top-5
- ``quality``   - answer quality: traces, error taxonomy, prediction card
- ``smoke``     - three end-to-end checks
"""

__all__ = ["datasets", "retrieval", "chunking", "quality", "smoke"]
