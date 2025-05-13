import argparse
import sys
import json
from rdflib import Graph, URIRef, RDF, Namespace
from collections import defaultdict
from typing import Dict, List, Tuple, Set
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, XSD
from .utils import extract_constraints_general
from .save_ontology_cache import load_ontology_cache

class consistencyValidator:
    def __init__(self):
        self.source_fns = {}  # {src: set of target classes}
        self.source_pvs = {}  # {src: {class: set(property paths)}}
        self.source_pvcs = {}  # {src: {(class, prop): set of (datatype, nodeKind, class)}}
        self.shape_sources = {}

    def extract_constraints(self):
        for src, g in self.sources.items():
            self.source_pvcs[src] = extract_constraints_general(g,src)

    def extract_all_shapes(self):
        for src, g in self.sources.items():
            focus_nodes = set()
            class_props = defaultdict(set)

            # source map: { class or (class, path, constraint) → list of sources }
            self.shape_sources.setdefault(src, {
                "focus_nodes": defaultdict(set),
                "property_paths": defaultdict(set)
                # "constraints": defaultdict(set)
            })

            for ns,_,cls in g.triples((None, SH.targetClass, None)):
                focus_nodes.add(cls)

                # Track dct:source at the NodeShape level
                node_sources = [str(s) for s in g.objects(ns, DCTERMS.source)]

                # 1. Handle directly attached sh:property
                ps_list = list(g.objects(ns, SH.property))
                if len(ps_list) == 0:
                    ps_list = [ns]
                for ps in ps_list:
                    path = next(g.objects(ps, SH.path), None)
                    if path:
                        class_props[cls].add(path)
                        # property path source
                        for s in g.objects(ps, DCTERMS.source):
                            self.shape_sources[src]["property_paths"][(cls, path)].add(str(s))

                # 2. Handle sh:or → [ sh:property ... ]
                for or_list in g.objects(ns, SH["or"]):
                    for or_item in self._parse_rdf_list(g, or_list):
                        for ps in g.objects(or_item, SH.property):
                            path = next(g.objects(ps, SH.path), None)
                            if path:
                                class_props[cls].add(path)
                                # property path source
                                for s in g.objects(ps, DCTERMS.source):
                                    self.shape_sources[src]["property_paths"][(cls, path)].add(str(s))
                # record node shape dct:source
                for s in node_sources:
                    self.shape_sources[src]["focus_nodes"][cls].add(s)
            
            self.source_fns[src] = focus_nodes
            self.source_pvs[src] = dict(class_props)
        self.extract_constraints()


    def _parse_rdf_list(self, g, head):
        """Parse an RDF collection (e.g., sh:or list)."""
        items = []
        while head and head != RDF.nil:
            first = next(g.objects(head, RDF.first), None)
            if first:
                items.append(first)
            head = next(g.objects(head, RDF.rest), None)
        return items

    def _extract_constraint(self, g, ps):
        d = next(g.objects(ps, SH.datatype), None)
        k = next(g.objects(ps, SH.nodeKind), None)
        c = next(g.objects(ps, SH['class']), None)
        if not c:
            node = next(g.objects(ps, SH.node), None)
            if node:
                c = next(g.objects(node, SH['class']), None)
        return (str(d) if d else None, str(k) if k else None, str(c) if c else None)

    def check_fni(self) -> Dict:
        """
        Detect Focus Node Inconsistency (TCI) across all sources.
        Generates detailed report using 'focusNodeDiffer', with 'presentIn' and 'missingIn' for each class.
        """
        owl_classes = self.source_fns.get("OWL", set())
        has_owl = "OWL" in self.source_fns
        all_sources = list(self.source_fns.keys())
        non_owl_sources = {src: fns for src, fns in self.source_fns.items() if src != "OWL"}

        diff_classes = set()

        if has_owl:
            # (1) Check if non-OWL sets are not mutually equal
            non_owl_fns = list(non_owl_sources.values())
            for i in range(len(non_owl_fns)):
                for j in range(i + 1, len(non_owl_fns)):
                    if non_owl_fns[i] != non_owl_fns[j]:
                        diff_classes |= (non_owl_fns[i] ^ non_owl_fns[j])
            # (2) Check for non-OWL classes not in OWL
            for src, fns in non_owl_sources.items():
                for cls in fns:
                    if cls not in owl_classes:
                        diff_classes.add(cls)
        else:
            # No OWL, check all pairwise equality
            values = list(self.source_fns.values())
            for i in range(len(values)):
                for j in range(i + 1, len(values)):
                    if values[i] != values[j]:
                        diff_classes |= (values[i] ^ values[j])

        if not diff_classes:
            return None

        result = {
            "type": "TCI",
            "differ": []
        }

        for cls in sorted(diff_classes):
            entry = {
                "targetClass": str(cls),
                "presentIn": {},
                "missingIn": {}
            }
            for src in all_sources:
                if cls in self.source_fns.get(src, set()):
                    # Get dct:source if available
                    if cls in self.shape_sources.get(src, {}).get("focus_nodes", {}):
                        entry["presentIn"][src] = sorted(self.shape_sources[src]["focus_nodes"][cls])
                    else:
                        entry["presentIn"][src] = []
                else:
                    entry["missingIn"][src] = []
            result["differ"].append(entry)

        return result

    def check_pvi(self) -> Dict:
        """
        Detect Property Value Inconsistency (PPI) across shared focus nodes in all sources.
        Generates detailed report using 'propertyValueDiffer', with 'presentIn' and 'missingIn' for each (focusNode, propertyPath) pair.
        """
        owl_pvs = self.source_pvs.get("OWL", {})
        has_owl = "OWL" in self.source_pvs
        all_sources = list(self.source_pvs.keys())
        non_owl_sources = {src: self.source_pvs[src] for src in self.source_pvs if src != "OWL"}

        # Step 1: compute shared focus nodes
        shared_classes = set.intersection(*[set(pvs.keys()) for pvs in self.source_pvs.values() if pvs])

        diff_pairs = set()

        if has_owl:
            for cls in shared_classes:
                # (1) Check mutual mismatch between non-OWL
                prop_sets = [non_owl_sources[src].get(cls, set()) for src in non_owl_sources]
                for i in range(len(prop_sets)):
                    for j in range(i + 1, len(prop_sets)):
                        if prop_sets[i] != prop_sets[j]:
                            diff_pairs |= {(cls, p) for p in prop_sets[i] ^ prop_sets[j]}
                # (2) Check if non-OWL props not ⊆ OWL
                for src in non_owl_sources:
                    for p in non_owl_sources[src].get(cls, set()):
                        if p not in owl_pvs.get(cls, set()):
                            diff_pairs.add((cls, p))
        else:
            for cls in shared_classes:
                prop_sets = [self.source_pvs[src].get(cls, set()) for src in self.source_pvs]
                for i in range(len(prop_sets)):
                    for j in range(i + 1, len(prop_sets)):
                        if prop_sets[i] != prop_sets[j]:
                            diff_pairs |= {(cls, p) for p in prop_sets[i] ^ prop_sets[j]}

        if not diff_pairs:
            return None

        result = {
            "type": "PPI",
            "differ": []
        }

        for cls, prop in sorted(diff_pairs):
            entry = {
                "targetClass": str(cls),
                "propertyPath": str(prop),
                "presentIn": {},
                "missingIn": {}
            }
            for src in all_sources:
                if prop in self.source_pvs.get(src, {}).get(cls, set()):
                    sources = self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,prop),[])
                    entry["presentIn"][src] = sorted(sources)
                else:
                    entry["missingIn"][src] = sorted(self.shape_sources[src]["focus_nodes"][cls])

            result["differ"].append(entry)

        return result

    def check_pvci(self) -> Dict:
        all_sources = list(self.source_pvcs.keys())

        shared_keys = set.intersection(*(set(cmap.keys()) for cmap in self.source_pvcs.values()))
        all_reports = []
        for cls_path in sorted(shared_keys):
            cls, prop = cls_path
            # constraint_type -> value -> present_sources
            constraint_presence = defaultdict(lambda: defaultdict(set))

            for src in all_sources:
                c_dict = self.source_pvcs[src].get(cls_path, {})
                for c_type in [SH.datatype, SH.nodeKind, SH["class"]]:
                    for val in c_dict.get(c_type, set()):
                        constraint_presence[c_type][val].add(src)

            for c_type, val_map in constraint_presence.items():
                for val, present_set in val_map.items():
                    if len(present_set) != len(all_sources):
                        presentIn = {src: sorted(self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,prop),[])) for src in present_set}
                        missingIn = {src: sorted(self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,prop),[])) for src in set(all_sources) - present_set}

                        if set(presentIn.keys()) == {"OWL"}:
                            continue

                        all_reports.append({
                            "targetClass": str(cls),
                            "propertyValue": str(prop),
                            "constraint": [str(c_type),str(val)],
                            "presentIn": presentIn,
                            "missingIn": missingIn
                        })

        return {"type": "VCI", "differ": all_reports} if all_reports else None



    def validate(self, source_files: Dict[str, str], owl_cache = None) -> List[Dict]:
        if not owl_cache:
            self.sources = {src: Graph().parse(path, format='ttl') for src, path in source_files.items() if path}
        else:
            self.sources = {src: Graph().parse(path, format='ttl') for src, path in source_files.items() if path and src != "OWL"}
            source_fns, source_pvs, shape_sources, constraint = load_ontology_cache(owl_cache)
            print(type(shape_sources))
            print(shape_sources.keys())
            self.shape_sources["OWL"] = shape_sources
            self.source_pvcs["OWL"] = constraint
            self.source_fns["OWL"] = source_fns
            self.source_pvs["OWL"] = source_pvs

        self.extract_all_shapes()
        report = []

        fni = self.check_fni()
        report.append(fni)

        pvi = self.check_pvi()
        report.append(pvi)

        pvci = self.check_pvci()
        report.append(pvci)
        
        return report

def main():
    parser = argparse.ArgumentParser(description="SHACL-driven Consistency Validator")
    parser.add_argument("--cm", type=str, help="Path to SHACL file generated from CM")
    parser.add_argument("--rml", type=str, help="Path to SHACL file generated from RML")
    parser.add_argument("--owl", type=str, help="Path to SHACL file generated from OWL ontology")
    parser.add_argument("--owl_cache", type=str, help="Path to cache file dict precomputed")
    parser.add_argument("--output", type=str, help="Path to write JSON report", default="report.json")
    args = parser.parse_args()

    source_files = {"CM": args.cm, "RML": args.rml, "OWL": args.owl}
    validator = consistencyValidator(source_files)
    report = validator.validate(args.owl_cache)
    with open(args.output, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Validation report written to {args.output}")

if __name__ == "__main__":
    main()
