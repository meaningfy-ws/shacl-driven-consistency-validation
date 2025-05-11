"""
Utiles functions for the CM2SHACL translation
"""

import json
import requests
import re
from collections import Counter
from rdflib import Graph, URIRef, Literal, BNode, RDF, RDFS, Namespace, SH
from collections import defaultdict
from rdflib.collection import Collection
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
    dctsource = URIRef("http://purl.org/dc/terms/source")
    dctsource_dict = defaultdict(list)

    # Collect dct:source info and remove
    for ps in graph.objects(None, SH.property):
        for _, _, o in graph.triples((ps, dctsource, None)):
            dctsource_dict[ps].append(o)
            graph.remove((ps, dctsource, o))
    for ps in graph.subjects(RDF.type, SH.PropertyShape):
        for _, _, o in graph.triples((ps, dctsource, None)):
            dctsource_dict[ps].append(o)
            graph.remove((ps, dctsource, o))

    # Find NodeShapes
    for ns in graph.subjects(RDF.type, SH.NodeShape):
        path_dict = defaultdict(list)

        # Group property shapes by path
        for ps in graph.objects(ns, SH.property):
            path = graph.value(ps, SH.path)
            if path:
                path_dict[path].append(ps)
            graph.remove((ps, SH.path, path))
            graph.remove((ns, SH.property, ps))

        # Add refined property shapes
        for path, shapes in path_dict.items():
            if len(shapes) == 1:
                graph.add((ns, SH.property, shapes[0]))
                graph.add((shapes[0], SH.path, path))
                for src in dctsource_dict[shapes[0]]:
                    graph.add((shapes[0], dctsource, src))
                continue
            
            # graph.remove((ps, SH.path, path))
            
            # Merge sh:in values
            in_values = set()
            nodeKinds = set()
            dataTypes = set()
            classes = set()
            for ps in shapes:
                for o in graph.objects(ps, SH["in"]):
                    for val in graph.items(o):
                        in_values.add(val)
                    collection = Collection(graph, o)
                    for item in collection:
                        pass  # Just to initialize the collection
                    collection.clear()
                    graph.remove((ps, SH["in"], o))
                for o in graph.objects(ps, SH["nodeKind"]):
                    nodeKinds.add(o)
                    graph.remove((ps, SH["nodeKind"], o))
                for o in graph.objects(ps, SH["datatype"]):
                    dataTypes.add(o)
                    graph.remove((ps, SH["datatype"], o))
                for o in graph.objects(ps, SH["class"]):
                    classes.add(o)
                    graph.remove((ps, SH["class"], o))

            # Create new merged shape
            merged_ps = BNode()
            # graph.add((merged_ps, RDF.type, SH.PropertyShape))
            graph.add((merged_ps, SH.path, path))

            if in_values:
                in_list = BNode()
                graph.add((merged_ps, SH["in"], in_list))
                in_bnode = in_list
                for val in list(in_values)[:-1]:
                    graph.add((in_bnode, RDF.first, val))
                    next_b = BNode()
                    graph.add((in_bnode, RDF.rest, next_b))
                    in_bnode = next_b
                graph.add((in_bnode, RDF.first, list(in_values)[-1]))
                graph.add((in_bnode, RDF.rest, RDF.nil))

            # Merge nodeKind, datatype, class using sh:or if needed
            or_shapes = []

            def add_or_shape(predicate, values):
                if not values:
                    return
                if len(values) == 1:
                    graph.add((merged_ps, predicate, next(iter(values))))
                else:
                    for v in values:
                        b = BNode()
                        graph.add((b, predicate, v))
                        or_shapes.append(b)

            add_or_shape(SH.nodeKind, nodeKinds)
            add_or_shape(SH.datatype, dataTypes)
            add_or_shape(SH["class"], classes)

            if or_shapes:
                or_bnode = BNode()
                graph.add((merged_ps, SH["or"], or_bnode))
                current = or_bnode
                for s in or_shapes[:-1]:
                    graph.add((current, RDF.first, s))
                    next_b = BNode()
                    graph.add((current, RDF.rest, next_b))
                    current = next_b
                graph.add((current, RDF.first, or_shapes[-1]))
                graph.add((current, RDF.rest, RDF.nil))

            graph.add((ns, SH.property, merged_ps))

            for ps in shapes:
                for src in dctsource_dict[ps]:
                    graph.add((merged_ps, dctsource, src))

    return graph

def combine_shapes_with_same_path_v1(graph):
    """
    Combines property shapes under the same node shape that have the same `sh:path` into a single property shape using `sh:or`.
    """
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