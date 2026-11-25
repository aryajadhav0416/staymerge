"""Constrained clustering for hotel matching enforcing supplier uniqueness."""
from collections import defaultdict
from typing import Dict, List, Set, Tuple


class ConstrainedUnionFind:
    """Union-Find with supplier uniqueness constraints.

    Safety rule:
    Never merge two clusters if that would put two rows of supplier A,
    or two rows of supplier C, into the same cluster.
    """

    def __init__(self, elements: List[str], supplier_map: Dict[str, str]):
        self.parent = {elem: elem for elem in elements}
        # Track suppliers present in each cluster root
        self.suppliers_in_cluster: Dict[str, Set[str]] = {}
        for elem in elements:
            sup = supplier_map.get(elem, "")
            self.suppliers_in_cluster[elem] = {sup} if sup in ("A", "C") else set()

    def find(self, i: str) -> str:
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def can_merge(self, i: str, j: str) -> bool:
        """Check if merging violates supplier A or C uniqueness."""
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i == root_j:
            return True

        sups_i = self.suppliers_in_cluster[root_i]
        sups_j = self.suppliers_in_cluster[root_j]

        # Violates if both clusters contain 'A' or both contain 'C'
        if "A" in sups_i and "A" in sups_j:
            return False
        if "C" in sups_i and "C" in sups_j:
            return False
        return True

    def union(self, i: str, j: str) -> bool:
        """Attempt to union two elements respecting safety constraints. Returns True if merged."""
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i == root_j:
            return True

        if not self.can_merge(i, j):
            return False

        # Merge root_j into root_i
        self.parent[root_j] = root_i
        self.suppliers_in_cluster[root_i].update(self.suppliers_in_cluster[root_j])
        return True


def cluster_records(
    row_ids: List[str],
    supplier_map: Dict[str, str],
    edges: List[Tuple[str, str]],
) -> Dict[str, str]:
    """Cluster rows by accepted edges enforcing supplier A and C uniqueness constraints.

    Returns:
        Mapping of row_id -> cluster_id (e.g. C0001, C0002, ...)
    """
    cuf = ConstrainedUnionFind(row_ids, supplier_map)

    for id_a, id_b in edges:
        cuf.union(id_a, id_b)

    cluster_id_map: Dict[str, str] = {}
    row_to_cluster: Dict[str, str] = {}
    cluster_counter = 1

    for rid in sorted(row_ids):
        root = cuf.find(rid)
        if root not in cluster_id_map:
            cluster_id_map[root] = f"C{cluster_counter:04d}"
            cluster_counter += 1
        row_to_cluster[rid] = cluster_id_map[root]

    return row_to_cluster
