"""
Utiles functions for the CM2SHACL translation
"""

import json
import requests
import re
from collections import Counter
from rdflib import Graph, URIRef, Literal, BNode, RDF, RDFS, Namespace, SH
from collections import defaultdict
SHACL = Namespace("http://www.w3.org/ns/shacl#")

def json_load(json_name):
    """
    Load a json file from a URL or a local file
    """
    if re.match(r'https?://', str(json_name)):
        return requests.get(json_name).json()
    with open(json_name, 'r', encoding='utf-8') as f:
        return json.load(f)

def combine_shapes_with_same_path(graph):
    """
    Combines property shapes under the same node shape that have the same `sh:path` into a single property shape using `sh:or`.
    """
    print("Combining shapes with the same path")
    node_shapes = graph.subjects(RDF.type, SH.NodeShape)
    for ns in node_shapes:
        path_dict = defaultdict(list)
        current_temp_dict = []
        # Collect property shapes under the same node shape by `sh:path` and "a sh:PropertyShape"
        for ps in graph.objects(ns, SH.property):
            path = graph.value(ps, SH.path)
            temp_dict = {}
            for s, p, o in graph.triples((ps, None, None)):
                temp_dict[p] = o
            if path:
                if temp_dict not in current_temp_dict:
                    path_dict[path].append(ps)
                    current_temp_dict.append(temp_dict)
                else:
                    graph = remove_subgraph(ps, graph)
        for ps in graph.subjects(RDF.type, SH.PropertyShape):
            path = graph.value(ps, SH.path)
            temp_dict = {}
            for s, p, o in graph.triples((ps, None, None)):
                temp_dict[p] = o
            if path:
                if temp_dict not in current_temp_dict:
                    path_dict[path].append(ps)
                    current_temp_dict.append(temp_dict)
                else:
                    graph = remove_subgraph(ps, graph)
        if path_dict:
            graph = addSHACLOR(ns, path_dict, graph)
    return graph

def remove_subgraph(ps, graph):
    """
    Remove duplicate property shapes
    """
    for s, p, o in graph.triples((ps, None, None)):
        graph.remove((s, p, o))
    for s, p, o in graph.triples((None, None, ps)):
        graph.remove((s, p, o))
    return graph

def addSHACLOR(ns, path_dict, g):
    for path, property_shapes in path_dict.items():
        if len(property_shapes) == 1:
            continue
        bn = BNode()
        g.add((ns,SH["or"],bn))
        for i in property_shapes[:-1]:
            g.remove((ns, SH.property, i))
            bn_prop = BNode()
            g.add((bn, RDF.first, bn_prop))
            g.add((bn_prop, SH.property, i))

            nextBn = BNode()
            g.add((bn,RDF.rest,nextBn))
            bn = nextBn
        g.remove((ns, SH.property, property_shapes[-1]))
        bn_prop = BNode()
        g.add((bn, RDF.first, bn_prop))
        g.add((bn_prop, SH.property, property_shapes[-1]))

        g.add((bn,RDF.rest,RDF.nil))
    return g