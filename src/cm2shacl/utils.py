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

def move_graph(identifier_to_remove:list, g_remove:Graph, g_add:Graph):
    for s,p,o in g_remove:
        if s in identifier_to_remove:
            g_remove.remove((s,p,o))
            g_add.add((s,p,o))
            if isinstance(o,BNode):
                move_graph([o], g_remove, g_add)
        elif o in identifier_to_remove:
           g_remove.remove((s,p,o))
           g_add.add((s,p,o))
    return g_remove, g_add


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
    # Collect all field identifiers
    dctsource = URIRef("http://purl.org/dc/terms/source")
    dctsource_dict = defaultdict(list)
    for ps in graph.objects(None, SH.property):
        for s, p, o  in graph.triples((ps, dctsource, None)):
            sources = dctsource_dict.get(s, [])
            sources.append(o)
            dctsource_dict[s] = sources
            graph.remove((s, p, o))
    for ps in graph.subjects(RDF.type, SH.PropertyShape):
        for s, p, o  in graph.triples((ps, dctsource, None)):
            sources = dctsource_dict.get(s, [])
            sources.append(o)
            dctsource_dict[s] = sources
            graph.remove((s, p, o))

    node_shapes = graph.subjects(RDF.type, SH.NodeShape)

    for ns in node_shapes:
        path_dict = defaultdict(list)
        current_temp_dict = {}
        # Collect property shapes under the same node shape by `sh:path` and "a sh:PropertyShape"
        for ps in graph.objects(ns, SH.property):
            path = graph.value(ps, SH.path)
            temp_dict = {}
            for s, p, o in graph.triples((ps, None, None)):
                temp_dict[p] = o
            if path:
                key = [k for k, v in current_temp_dict.items() if v == temp_dict]
                if key == []:
                    path_dict[path].append(ps)
                    current_temp_dict[ps] = temp_dict
                    for dctsourceID in dctsource_dict[ps]:
                        graph.add((ps, dctsource, dctsourceID))
                else:
                    graph = remove_subgraph(ps, graph)
                    for dctsourceID in dctsource_dict[ps]:
                        graph.add((key[0], dctsource, dctsourceID))

        for ps in graph.subjects(RDF.type, SH.PropertyShape):
            path = graph.value(ps, SH.path)
            temp_dict = {}
            for s, p, o in graph.triples((ps, None, None)):
                temp_dict[p] = o
            if path:
                key = [k for k, v in current_temp_dict.items() if v == temp_dict]
                if key == []:
                    path_dict[path].append(ps)
                    current_temp_dict[ps] = temp_dict
                    for dctsourceID in dctsource_dict[ps]:
                        graph.add((ps, dctsource, dctsourceID))
                else:
                    graph = remove_subgraph(ps, graph)
                    for dctsourceID in dctsource_dict[ps]:
                        graph.add((key[0], dctsource, dctsourceID))
        if path_dict:
            graph = addSHACLOR(ns, path_dict, graph)
            for _, property_shapes in path_dict.items():
                for ps in property_shapes:
                    for dctsourceID in dctsource_dict[ps]:
                        graph.add((ps, dctsource, dctsourceID))
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