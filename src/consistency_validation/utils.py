from rdflib import Graph, RDF, URIRef, Literal, Namespace
from rdflib.namespace import SH
from collections import defaultdict
from itertools import zip_longest
from typing import Dict, List, Tuple, Set
from rdflib import RDF, SH
from collections import defaultdict

def extract_constraint_tuple(graph, shape):
    """
    Extract a single (datatype, nodeKind, class) constraint.
    If no_or=True: treat shape as atomic.
    """
    d = graph.value(subject=shape, predicate=SH.datatype)
    k = graph.value(subject=shape, predicate=SH.nodeKind)
    c = graph.value(subject=shape, predicate=SH["class"])

    # sh:node 替代 class
    if not c:
        node = graph.value(subject=shape, predicate=SH.node)
        if node:
            c = graph.value(subject=node, predicate=SH["class"])

    return (
        str(d) if d else None,
        str(k) if k else None,
        str(c) if c else None,
    )

def extract_constraints_general(graph, source_type):
    """
    For each (targetClass, path), extract all constraints.
    Return: dict mapping (class, path) -> set of (datatype, nodeKind, class)
    """
    shape_map = defaultdict(list) 
    # Step 1: 构建 (targetClass, path) 到 shape 的映射
    for s,_,cls in graph.triples((None,SH.targetClass,None)):
            for ps in graph.objects(s, SH.property):
                    path = graph.value(ps, SH.path)
                    if path:
                        shape_map[(cls, path)].append(ps)
            path = graph.value(s, SH.path)
            if path:
                shape_map[(cls, path)].append(s)
    constraint_map = {}
    
    for (cls, path), shape_list in shape_map.items():
        datatype_set = set()
        nodekind_set = set()
        class_set = set()
        for shape in shape_list:
            d, k, c = extract_constraint_tuple(graph, shape)
            if d: datatype_set.add(d)
            if k: nodekind_set.add(k)
            if k == str(SH.IRIOrLiteral): 
                nodekind_set.add(str(SH.IRI))
                nodekind_set.add(str(SH.Literal))
            if k == str(SH.BlankNodeOrIRI):
                nodekind_set.add(str(SH.IRI))
                nodekind_set.add(str(SH.BlankNode))
            if k == str(SH.BlankNodeOrLiteral):
                nodekind_set.add(str(SH.Literal))
                nodekind_set.add(str(SH.BlankNode))
            if c: class_set.add(c)
            or_node = graph.value(subject=shape, predicate=SH["or"])
            if or_node:
                for alt in graph.items(or_node):
                    d, k, c = extract_constraint_tuple(graph, alt)
                    if d: datatype_set.add(d)
                    if k: nodekind_set.add(k)
                    if c: class_set.add(c)
        constraint_map[(cls, path)] = {SH.datatype: datatype_set,
                                        SH.nodeKind: nodekind_set,
                                        SH["class"]: class_set}
    return constraint_map

    

def extract_constraints_general_(graph, source_type):
    """
    For each (targetClass, path), extract all constraints.
    Return: dict mapping (class, path) -> set of (datatype, nodeKind, class)
    """
    shape_map = defaultdict(list)

    # Step 1: 构建 (targetClass, path) 到 shape 的映射
    for s,_,cls in graph.triples((None,SH.targetClass,None)):
            for ps in graph.objects(s, SH.property):
                    path = graph.value(ps, SH.path)
                    if path:
                        shape_map[(cls, path)].append(ps)
            path = graph.value(s, SH.path)
            if path:
                    shape_map[(cls, path)].append(s)

    # Step 2: 每个 (class, path) 分别处理不同来源
    constraint_map = {}


    for (cls, path), shape_list in shape_map.items():
        constraint_set = set()

        if source_type in {"CM", "RML"}:
            for shape in shape_list:
                or_node = graph.value(subject=shape, predicate=SH["or"])
                or_group = []
                if or_node:
                    for alt in graph.items(or_node):
                        d, k, c = extract_constraint_tuple(graph, alt)
                        single = []
                        if d: single.append((SH.datatype, d))
                        if k: single.append((SH.nodeKind, k))
                        if c: single.append((SH["class"], c))
                        if single:
                            or_group.append(single)
                d, k, c = extract_constraint_tuple(graph, shape)
                hashable_or_group = tuple(tuple(group) for group in or_group)
                constraint_set.add((d, k, c, hashable_or_group))

        else:  # OWL special case
            datatype_set = set()
            nodekind_set = set()
            class_set = set()

            for shape in shape_list:
                d, k, c = extract_constraint_tuple(graph, shape)
                if d: datatype_set.add(d)
                if k: nodekind_set.add(k)
                if c: class_set.add(c)

            or_group = []

            if len(nodekind_set) == 2:
                if "http://www.w3.org/ns/shacl#IRI" in nodekind_set and "http://www.w3.org/ns/shacl#IRIOrLiteral" in nodekind_set:
                    nodekind_set.remove("http://www.w3.org/ns/shacl#IRIOrLiteral")

                elif "http://www.w3.org/ns/shacl#Literal" in nodekind_set and "http://www.w3.org/ns/shacl#IRIOrLiteral" in nodekind_set:
                    nodekind_set.remove("http://www.w3.org/ns/shacl#IRIOrLiteral")

            # 单个值保留在前三元组，多值则放入 or 组中
            d_val = next(iter(datatype_set)) if len(datatype_set) == 1 else None
            k_val = next(iter(nodekind_set)) if len(nodekind_set) == 1 else None
            c_val = next(iter(class_set)) if len(class_set) == 1 else None

            or_group = []
            if len(datatype_set) > 1:
                for d in datatype_set:
                    single = []
                    if d: single.append((SH.datatype, d))
                    or_group.append(single)
                # or_group.append((SH.datatype, d) for d in datatype_set)
            if len(nodekind_set) > 1:
                for k in nodekind_set:
                    single = []
                    if k: single.append((SH.nodeKind, k))
                    or_group.append(single)
                # or_group.append((SH.nodeKind, k) for k in nodekind_set)
            if len(class_set) > 1:
                for c in class_set:
                    single = []
                    if c: single.append((SH["class"], c))
                    or_group.append(single)
                # or_group.append((SH["class"], c) for c in class_set)
            hashable_or_group = tuple(tuple(group) for group in or_group)
            constraint_set.add((d_val, k_val, c_val, hashable_or_group))

        constraint_map[(cls, path)] = constraint_set
    return constraint_map


def decompose_constraint_tuple(constraint):
    """将一个constraint拆解成非or和or部分"""

    d, k, c, or_groups = constraint
    components = []

    if d is not None:
        components.append((SH.datatype, d))
    if k is not None:
        components.append((SH.nodeKind, k))
    if c is not None:
        components.append((SH["class"], c))

    return components, or_groups or []

def convert_sets_to_lists(obj):
    if isinstance(obj, dict):
        return {k: convert_sets_to_lists(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_sets_to_lists(v) for v in obj]
    elif isinstance(obj, set):
        return list(obj)
    else:
        return obj