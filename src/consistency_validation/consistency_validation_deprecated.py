import argparse
import sys
import json
from rdflib import Graph, URIRef, RDF, Namespace
from collections import defaultdict
from typing import Dict, List, Tuple, Set
import logging
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, XSD
from .utils import extract_constraints_general, decompose_constraint_tuple
import time

class consistencyValidator:
    def __init__(self, source_files: Dict[str, str]):
        # source_files is a dict like {"CM": "cm.ttl", "RML": "rml.ttl", "OWL": "ontology.ttl"}
        self.sources = {src: Graph().parse(path, format='ttl') for src, path in source_files.items() if path}
        self.source_fns = {}  # {src: set of target classes}
        self.source_pvs = {}  # {src: {class: set(property paths)}}
        self.source_pvcs = {}  # {src: {(class, prop): set of (datatype, nodeKind, class)}}
        self.shape_sources = {}
    def extract_focus_nodes(self):
        for src, g in self.sources.items():
            focus_nodes = set()
            for s, _, cls in g.triples((None, SH.targetClass, None)):
                focus_nodes.add(cls)
            self.source_fns[src] = focus_nodes

    def extract_property_values(self):
        for src, g in self.sources.items():
            class_props = defaultdict(set)
            for ns,_,cls in g.triples((None,SH.targetClass,None)):
                for ps in g.objects(ns, SH.property):
                    for path in g.objects(ps, SH.path):
                        class_props[cls].add(path)
                for ps in g.objects(ns, SH.path):
                    path = g.value(ps, SH.path)
                    if path:
                        class_props[cls].add(path)
            self.source_pvs[src] = dict(class_props)

    def extract_constraints(self):
        for src, g in self.sources.items():
            self.source_pvcs[src] = extract_constraints_general(g,src)
        
    def _extract_constraints(self):
        for src, g in self.sources.items():
            constraint_map = defaultdict(set)
            for ns in g.subjects(RDF.type, SH.NodeShape):
                for cls in g.objects(ns, SH.targetClass):
                    for ps in g.objects(ns, SH.property):
                        for path in g.objects(ps, SH.path):
                            d = next(g.objects(ps, SH.datatype), None)
                            k = next(g.objects(ps, SH.nodeKind), None)
                            c = next(g.objects(ps, SH['class']), None)
                            # sh:node with nested node shape implies class constraint
                            if not c:
                                node = next(g.objects(ps, SH.node), None)
                                if node:
                                    c = next(g.objects(node, SH['class']), None)
                            constraint_map[(cls, path)].add((str(d) if d else None,
                                                             str(k) if k else None,
                                                             str(c) if c else None))
            self.source_pvcs[src] = dict(constraint_map)

    def extract_all_shapes(self):
        for src, g in self.sources.items():
            focus_nodes = set()
            class_props = defaultdict(set)
            constraint_map = defaultdict(set)

            # source map: { class or (class, path, constraint) → list of sources }
            self.shape_sources.setdefault(src, {
                "focus_nodes": defaultdict(set),
                "property_paths": defaultdict(set),
                "constraints": defaultdict(set)
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
                        # constraint = self._extract_constraint(g, ps)
                        # constraint_map[(cls, path)].add(constraint)

                        # property path source
                        for s in g.objects(ps, DCTERMS.source):
                            self.shape_sources[src]["property_paths"][(cls, path)].add(str(s))
                        # # constraint source
                        # for s in g.objects(ps, DCTERMS.source):
                        #     self.shape_sources[src]["constraints"][(cls, path, constraint)].add(str(s))

                # 2. Handle sh:or → [ sh:property ... ]
                for or_list in g.objects(ns, SH["or"]):
                    for or_item in self._parse_rdf_list(g, or_list):
                        for ps in g.objects(or_item, SH.property):
                            path = next(g.objects(ps, SH.path), None)
                            if path:
                                class_props[cls].add(path)
                                # constraint = self.extract_constraint(g, ps)
                                # constraint_map[(cls, path)].add(constraint)

                                # property path source
                                for s in g.objects(ps, DCTERMS.source):
                                    self.shape_sources[src]["property_paths"][(cls, path)].add(str(s))
                                # constraint source
                                # for s in g.objects(ps, DCTERMS.source):
                                #     self.shape_sources[src]["constraints"][(cls, path, constraint)].add(str(s))

                # record node shape dct:source
                for s in node_sources:
                    self.shape_sources[src]["focus_nodes"][cls].add(s)
            
            self.source_fns[src] = focus_nodes
            self.source_pvs[src] = dict(class_props)
        start_time = time.time()
        self.extract_constraints()
        end_time = time.time()
        print(f"extract_constraints() {end_time - start_time:.2f} seconds")


    def _extract_constraint(self, g, ps):
        d = next(g.objects(ps, SH.datatype), None)
        k = next(g.objects(ps, SH.nodeKind), None)
        c = next(g.objects(ps, SH['class']), None)
        if not c:
            node = next(g.objects(ps, SH.node), None)
            if node:
                c = next(g.objects(node, SH['class']), None)
        return (str(d) if d else None, str(k) if k else None, str(c) if c else None)

    def _parse_rdf_list(self, g, head):
        """Parse an RDF collection (e.g., sh:or list)."""
        items = []
        while head and head != RDF.nil:
            first = next(g.objects(head, RDF.first), None)
            if first:
                items.append(first)
            head = next(g.objects(head, RDF.rest), None)
        return items

    def check_fni(self) -> Dict:
        """
        Detect Focus Node Inconsistency (FNI) across all sources.
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
            "type": "FNI",
            "focusNodeDiffer": []
        }

        for cls in sorted(diff_classes):
            entry = {
                "focusNode": str(cls),
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
            result["focusNodeDiffer"].append(entry)

        return result

    def check_pvi(self) -> Dict:
        """
        Detect Property Value Inconsistency (PVI) across shared focus nodes in all sources.
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
            "type": "PVI",
            "propertyValueDiffer": []
        }

        for cls, prop in sorted(diff_pairs):
            entry = {
                "focusNode": str(cls),
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

            result["propertyValueDiffer"].append(entry)

        return result

    def check_pvci(self) -> Dict:
        all_sources = list(self.source_pvcs.keys())

        shared_keys = set.intersection(*(set(cmap.keys()) for cmap in self.source_pvcs.values()))
        all_reports = []
        for cls_path in sorted(shared_keys):
            cls, prop = cls_path
            # constraint_type -> value -> present_sources
            constraint_presence = defaultdict(lambda: defaultdict(set))

            # 填充每个 constraint type 和 value 的出现情况
            for src in all_sources:
                c_dict = self.source_pvcs[src].get(cls_path, {})
                for c_type in [SH.datatype, SH.nodeKind, SH["class"]]:
                    for val in c_dict.get(c_type, set()):
                        constraint_presence[c_type][val].add(src)

            # 遍历所有 constraint type 和所有值，计算每个值的 presentIn / missingIn
            for c_type, val_map in constraint_presence.items():
                for val, present_set in val_map.items():
                    if len(present_set) != len(all_sources):
                        # 存在缺失
                        presentIn = {src: sorted(self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,prop),[])) for src in present_set}
                        missingIn = {src: sorted(self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,prop),[])) for src in set(all_sources) - present_set}

                        if set(presentIn.keys()) == {"OWL"}:
                            continue

                        all_reports.append({
                            "focusNode": str(cls),
                            "propertyValue": str(prop),
                            "constraint": [str(c_type),str(val)],
                            "presentIn": presentIn,
                            "missingIn": missingIn
                        })

        return {"type": "PVCI", "constraintDiffer": all_reports} if all_reports else None



    # def check_pvci(self) -> Dict:
    #     has_owl = "OWL" in self.source_pvcs
    #     all_sources = list(self.source_pvcs.keys())
    #     non_owl_sources = [s for s in all_sources if s != "OWL"]

    #     shared_classes = set.intersection(*[set(pvs.keys()) for pvs in self.source_pvs.values()])
        
    #     all_pvci_reports = []

    #     all_keys = set()
    #     for src in self.source_pvcs:
    #         all_keys.update(self.source_pvcs[src].keys())  # (cls, path)

    #     report = []
    #     for cls in sorted(shared_classes):
    #         shared_props = set.intersection(*[
    #             set(self.source_pvs[src].get(cls, set())) for src in self.source_pvs
    #         ])
    #         for path in sorted(shared_props):
    #             constraints_by_src = {
    #                 src: self.source_pvcs[src].get((cls, path), set())
    #                 for src in all_sources
    #             }
    #             # 汇总所有 component 和 or groups
    #             all_simple = set()
    #             all_or_groups = set()
    #             for constraint_set in constraints_by_src.values():
    #                 for c in constraint_set:
    #                     simple, ors = decompose_constraint_tuple(c)
    #                     all_simple.update(simple)
    #                     all_or_groups.update(tuple(sorted(g)) for g in ors)

    #             # 分别检查 component 和 or group
    #             for item in all_simple:
    #                 present_in, missing_in = {}, {}
    #                 for src in all_sources:
    #                     found = False
    #                     for c in constraints_by_src.get(src, set()):
    #                         simple, _ = decompose_constraint_tuple(c)      
    #                         if item in simple:
    #                             found = True
    #                             break
    #                     if found:
    #                         # present_in[src] = self.shape_sources.get(src, {}).get("constraints", {}).get((cls, path, c), [])
    #                         present_in[src] = sorted(self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,path),[]))
    #                     else:
    #                         if item[0] == SH.nodeKind:
    #                             for c in constraints_by_src.get(src, set()):
    #                                 simple, _ = decompose_constraint_tuple(c)   
    #                                 if (SH.nodeKind, "http://www.w3.org/ns/shacl#IRIOrLiteral") in simple:
    #                                     found = True
    #                                     break
    #                         else: 
    #                             for c in constraints_by_src.get(src, set()):
    #                                 _, ors = decompose_constraint_tuple(c)   
    #                                 found = tuple([item]) in ors
                         
    #                         if found:
    #                             present_in[src] = sorted(self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,path),[]))
    #                         # missing_in[src] = self.shape_sources.get(src, {}).get("property_paths", {}).get((cls, path), [])
    #                         else:
    #                             missing_in[src] = sorted(self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,path),[]))
    #                 if missing_in:
    #                     if has_owl and set(present_in.keys()) == {"OWL"}:
    #                         continue
    #                     if item[0] == SH.nodeKind and str(item[1]) == "http://www.w3.org/ns/shacl#IRIOrLiteral":
    #                         continue
    #                     if item[0] == SH.datatype and str(item[1]) == "http://www.w3.org/2001/XMLSchema#string" and set(missing_in.keys()) == {"OWL"}:
    #                         continue
    #                     report.append({
    #                         "focusNode": str(cls),
    #                         "propertyValue": str(path),
    #                         "constraint": list(item),
    #                         "presentIn": present_in,
    #                         "missingIn": missing_in
    #                     })

    #             for group in all_or_groups:
    #                 present_in, missing_in = {}, {}
    #                 for src in all_sources:
    #                     found = False
    #                     for c in constraints_by_src.get(src, set()):
    #                         _, ors = decompose_constraint_tuple(c)
    #                         if any(set(group) == set(g) for g in ors):
    #                             found = True
    #                             break
    #                     if found:
    #                         present_in[src] = sorted(self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,path),[]))
    #                     else:
    #                         # missing_in[src] = self.shape_sources.get(src, {}).get("property_paths", {}).get((cls, path), [])
    #                         if item[0] == SH.nodeKind:
    #                             for c in constraints_by_src.get(src, set()):
    #                                 simple, _ = decompose_constraint_tuple(c)   
    #                                 if (SH.nodeKind, "http://www.w3.org/ns/shacl#IRIOrLiteral") in simple:
    #                                     found = True
    #                                     break
    #                         if found:
    #                             present_in[src] = sorted(self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,path),[]))
    #                         # missing_in[src] = self.shape_sources.get(src, {}).get("property_paths", {}).get((cls, path), [])
    #                         else:
    #                             missing_in[src] = sorted(self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,path),[]))
    #                 if missing_in:
                        
    #                     if has_owl and set(present_in.keys()) == {"OWL"}:
    #                         continue
    #                     report.append({
    #                         "focusNode": str(cls),
    #                         "propertyValue": str(path),
    #                         # "constraint": [None, None, None, [list(group)]],
    #                         "constraint": list(group),
    #                         "presentIn": present_in,
    #                         "missingIn": missing_in
    #                     })

    #     if not report:
    #         return None

    #     return {
    #         "type": "PVCI",
    #         "constraintDiffer": report
    #     }


    def _check_pvci(self) -> Dict:
        """
        Detect Property Value Constraint Inconsistency (PVCI).
        OWL is treated as an upper bound: other sources can define fewer constraints, but not more.
        """
        has_owl = "OWL" in self.source_pvs
        all_sources = list(self.source_pvs.keys())
        non_owl_sources = [s for s in all_sources if s != "OWL"]
        shared_classes = set.intersection(*[set(pvs.keys()) for pvs in self.source_pvs.values()])
        
        all_pvci_reports = []

        for cls in sorted(shared_classes):
            shared_props = set.intersection(*[
                set(self.source_pvs[src].get(cls, set())) for src in self.source_pvs
            ])
            for prop in sorted(shared_props):
                constraints_by_src = {
                    src: self.source_pvcs.get(src, {}).get((cls, prop), set())
                    for src in self.sources
                }
                all_constraints = set().union(*constraints_by_src.values())
                if has_owl:
                    owl_constraints = constraints_by_src.get("OWL", set())

                    # 记录所有非OWL来源的 extra constraints: constraint -> list of sources
                    constraint_to_sources = {}
                    for src in non_owl_sources:
                        extra_constraints = constraints_by_src[src] - owl_constraints
                        for constraint in extra_constraints:
                            constraint_to_sources.setdefault(constraint, []).append(src)

                    # 合并输出：每个 constraint 只报告一次 presentIn，避免重复
                    for constraint, src_list in constraint_to_sources.items():
                        present_in = {}
                        for src in src_list:
                            present_in[src] = sorted(self.shape_sources.get(src, {}).get("constraints", {}).get((cls, prop, constraint), []))
                        all_pvci_reports.append({
                            "focusNode": str(cls),
                            "propertyValue": str(prop),
                            "constraint": list(constraint),
                            "presentIn": present_in,
                            "missingIn": {
                                "OWL": []
                                }
                        })


                    # Check consistency among non-OWL sources (must be mutually equal)
                    for i in range(len(non_owl_sources)):
                        for j in range(i + 1, len(non_owl_sources)):
                            src_i, src_j = non_owl_sources[i], non_owl_sources[j]
                            if constraints_by_src[src_i] != constraints_by_src[src_j]:
                                all_unique = constraints_by_src[src_i].union(constraints_by_src[src_j])
                                shared = constraints_by_src[src_i].intersection(constraints_by_src[src_j])
                                diff = all_unique - shared
                                for constraint in diff:
                                    present_in = {}
                                    missing_in = {}
                                    for src in [src_i, src_j]:
                                        if constraint in constraints_by_src[src]:
                                            dct = self.shape_sources.get(src, {}).get("constraints", {}).get((cls,prop,constraint), [])
                                            present_in[src] = sorted(dct)
                                        else:
                                            dct = self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,prop),[])
                                            missing_in[src] = sorted(dct)
                                    # if constraint[0] == str(RDF.langString) or constraint[0] == str(XSD.anyURI):
                                    #     pass

                                    all_pvci_reports.append({
                                        "focusNode": str(cls),
                                        "propertyValue": str(prop),
                                        "constraint": list(constraint),
                                        "presentIn": present_in,
                                        "missingIn": missing_in
                                    })
                else:
                    # No OWL, compare all sources mutually
                    for i in range(len(all_sources)):
                        for j in range(i + 1, len(all_sources)):
                            src_i, src_j = all_sources[i], all_sources[j]
                            if constraints_by_src[src_i] != constraints_by_src[src_j]:
                                all_unique = constraints_by_src[src_i].union(constraints_by_src[src_j])
                                shared = constraints_by_src[src_i].intersection(constraints_by_src[src_j])
                                diff = all_unique - shared
                                for constraint in diff:
                                    present_in = {}
                                    missing_in = {}
                                    for src in [src_i, src_j]:
                                        if constraint in constraints_by_src[src]:
                                            dct = self.shape_sources.get(src, {}).get("constraints", {}).get((cls,prop,constraint), [])
                                            present_in[src] = sorted(dct)
                                        else:
                                            dct = self.shape_sources.get(src, {}).get("property_paths", {}).get((cls,prop),[])
                                            missing_in[src] = sorted(dct)
                                    # if constraint[0] == str(RDF.langString) or constraint[0] == str(XSD.anyURI):
                                    #     pass
                                    all_pvci_reports.append({
                                        "focusNode": str(cls),
                                        "propertyValue": str(prop),
                                        "constraint": list(constraint),
                                        "presentIn": present_in,
                                        "missingIn": missing_in
                                    })

        if not all_pvci_reports:
            return None

        return {
            "type": "PVCI",
            "constraintDiffer": all_pvci_reports
        }


    def check_pvci_(self) -> Dict:
        """
        Detect Property Value Constraint Inconsistency (PVCI).
        Reports constraint-level differences with presentIn/missingIn + dct:source support.
        """
        has_owl = "OWL" in self.source_pvs
        all_sources = list(self.source_pvs.keys())
        shared_classes = set.intersection(*[set(pvs.keys()) for pvs in self.source_pvs.values()])
        
        all_pvci_reports = []

        for cls in sorted(shared_classes):
            shared_props = set.intersection(*[
                set(self.source_pvs[src].get(cls, set())) for src in self.source_pvs
            ])
            for prop in sorted(shared_props):
                # Step 1: collect constraints for (cls, prop) across all sources
                constraints_by_src = {
                    src: self.source_pvcs.get(src, {}).get((cls, prop), set())
                    for src in self.sources
                }
                # Step 2: compute all unique constraint tuples
                all_constraints = set().union(*constraints_by_src.values())

                # Step 3: for each constraint, check presence/absence per source
                for constraint in all_constraints:
                    present_in = {}
                    missing_in = {}

                    for src in self.sources:
                        present = constraint in constraints_by_src.get(src, set())
                        if present:
                            # get dct:source where this (cls, prop) and constraint appears
                            dct_list = self.shape_sources.get(src, {}).get("constraints", {}).get((cls,prop,constraint), [])
                            present_in[src] = sorted(dct_list)
                        else:
                            missing_in[src] = []

                    # Only report if constraint not universally present
                    
                    if len(present_in) != len(self.sources):
                        # if constraint[0] == str(RDF.langString) or constraint[0] == str(XSD.anyURI):
                        #     pass
                        
                        all_pvci_reports.append({
                            "focusNode": str(cls),
                            "propertyValue": str(prop),
                            "constraint": list(constraint),
                            "presentIn": present_in,
                            "missingIn": missing_in
                        })

        if not all_pvci_reports:
            return None

        return {
            "type": "PVCI",
            "constraintDiffer": all_pvci_reports
        }



    def validate(self) -> List[Dict]:
        start_time = time.time()    
        self.extract_all_shapes()
        end_time = time.time()  
        print(f"extract_all_shapes(){end_time - start_time:.2f} seconds")
        report = []

        start_time = time.time()
        fni = self.check_fni()
        end_time = time.time()
        print(f"check_fni(){end_time - start_time:.2f} seconds")
        report.append(fni)

        start_time = time.time()
        pvi = self.check_pvi()
        end_time = time.time()
        print(f"check_pvi(){end_time - start_time:.2f} seconds")
        report.append(pvi)

        start_time = time.time()
        pvci = self.check_pvci()
        end_time = time.time()
        print(f"check_pvci(){end_time - start_time:.2f} seconds")
        report.append(pvci)
        
        return report

def main():
    parser = argparse.ArgumentParser(description="SHACL-driven Consistency Validator")
    parser.add_argument("--cm", type=str, help="Path to SHACL file generated from CM")
    parser.add_argument("--rml", type=str, help="Path to SHACL file generated from RML")
    parser.add_argument("--owl", type=str, help="Path to SHACL file generated from OWL ontology")
    parser.add_argument("--output", type=str, help="Path to write JSON report", default="report.json")
    args = parser.parse_args()

    source_files = {"CM": args.cm, "RML": args.rml, "OWL": args.owl}
    validator = consistencyValidator(source_files)
    report = validator.validate()
    with open(args.output, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Validation report written to {args.output}")

if __name__ == "__main__":
    main()
