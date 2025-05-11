import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'consistency_validation')))

import pickle
from utils import extract_constraints_general
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, DCTERMS, SH
from collections import defaultdict

def save_ontology_cache(filename, focus_nodes, class_props, shape_sources, constraints):
    data = {
        "source_fns": focus_nodes,
        "source_pvs": class_props,
        "shape_sources": shape_sources,
        "constraints": constraints,
    }
    with open(filename, "wb") as f:
        pickle.dump(data, f)
    print(f"Ontology SHACL cache saved to {filename}")

def load_ontology_cache(filename):
    with open(filename, "rb") as f:
        data = pickle.load(f)
    return data["source_fns"], data["source_pvs"], data["shape_sources"], data["constraints"]

def parse_rdf_list(g, head):
    """Parse an RDF collection (e.g., sh:or list)."""
    items = []
    while head and head != RDF.nil:
        first = next(g.objects(head, RDF.first), None)
        if first:
            items.append(first)
        head = next(g.objects(head, RDF.rest), None)
    return items

def get_ontology_cache_filename(ontology_path, save_path):
        focus_nodes = set()
        class_props = defaultdict(set)
        shape_sources = {
            "focus_nodes": defaultdict(set),
            "property_paths": defaultdict(set)
        }

        g = Graph().parse(ontology_path)
        for ns,_,cls in g.triples((None, SH.targetClass, None)):
            focus_nodes.add(cls)
            node_sources = [str(s) for s in g.objects(ns, DCTERMS.source)]
            ps_list = list(g.objects(ns, SH.property))
            if len(ps_list) == 0:
                ps_list = [ns]
            for ps in ps_list:
                path = next(g.objects(ps, SH.path), None)
                if path:
                    class_props[cls].add(path)
                    for s in g.objects(ps, DCTERMS.source):
                        shape_sources["property_paths"][(cls, path)].add(str(s))

            # 2. Handle sh:or → [ sh:property ... ]
            for or_list in g.objects(ns, SH["or"]):
                for or_item in parse_rdf_list(g, or_list):
                    for ps in g.objects(or_item, SH.property):
                        path = next(g.objects(ps, SH.path), None)
                        if path:
                            class_props[cls].add(path)
                            # property path source
                            for s in g.objects(ps, DCTERMS.source):
                                shape_sources["property_paths"][(cls, path)].add(str(s))
            # record node shape dct:source
            for s in node_sources:
                shape_sources["focus_nodes"][cls].add(s)
        constraints = extract_constraints_general(g, "OWL")
        save_ontology_cache(save_path, focus_nodes, class_props, shape_sources, constraints)
        
if __name__ == "__main__":
    ontology_path = "evaluation/eforms/ontology/shacl_ontology.ttl"
    save_path = "evaluation/eforms/ontology/cache.pkl"
    get_ontology_cache_filename(ontology_path, save_path)
    

    ontology_path = "evaluation/standardForms/ontology/shacl_ontology.ttl"
    save_path = "evaluation/standardForms/ontology/cache.pkl"
    get_ontology_cache_filename(ontology_path, save_path)
    pass