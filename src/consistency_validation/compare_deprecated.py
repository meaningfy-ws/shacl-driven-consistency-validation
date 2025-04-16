import rdflib
from rdflib import Graph, URIRef, RDF, BNode
from rdflib.namespace import SH, RDF, XSD
from pandas import DataFrame
import json
import os
from collections import defaultdict

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

class SHACLConsistencyChecker:
    def __init__(self):
        self.in_both_graph = Graph()
        self.in_first_graph = Graph()
        self.in_second_graph = Graph()
        self.in_first_report = []
        self.in_second_report = []
        self.rml_validation_report = {"Missed":{"Number":0, "TriplesMap":{}}, "Conflict":{"Number":0, "TriplesMap":{}}, "Extra":{"Number":0, "TriplesMap":{}}}

        self.inconsistency_level1 = "MISS"
        self.inconsistency_level2 = "CONFLICT"

        self.constriants_check = [SH.datatype, SH.nodeKind, SH["class"], SH.targetClass, SH.path]

    def index_shape_graph(self):
        """
        Build an index of node shapes in the second graph by target class
        """
        index = dict()
        for ns in self.g2.subjects(RDF.type, URIRef("http://www.w3.org/ns/shacl#NodeShape")):
            target_class = self.g2.value(ns, URIRef("http://www.w3.org/ns/shacl#targetClass"))
            if target_class:
                index[target_class] = index.get(target_class, [])
                index[target_class].append({ns:{}})
                # Index property shapes asscoiated with this node shape directly via sh:property
                for ps in self.g2.objects(ns, URIRef("http://www.w3.org/ns/shacl#property")):
                    path = self.g2.value(ps, URIRef("http://www.w3.org/ns/shacl#path"))
                    index[target_class][-1][ns][path] = ps
                # Index property shapes associated with this node shape via sh:or
                for or_bn in self.g2.objects(ns, SH["or"]):
                    or_shapes = self.or_shape(self.g2, or_bn, {})
                    if not index[target_class][-1][ns].get(SH["or"]):
                        index[target_class][-1][ns][SH["or"]] = {or_bn: or_shapes}
                    else:
                        index[target_class][-1][ns][SH["or"]][or_bn] = or_shapes
        return index

    def or_shape(self, g, or_bn, or_shapes:dict):
        # return a list of property shapes bnodes
        while or_bn!= RDF.nil:
            bn = g.value(or_bn, RDF.first)
            bn = g.value(bn, SH.property)
            p = g.value(bn, SH.path)
            temp_l = or_shapes.get(p, [])
            temp_l.append(bn)
            or_shapes[p] = temp_l
            or_bn = g.value(or_bn, RDF.rest)
            or_shapes = self.or_shape(g, or_bn, or_shapes)
        return or_shapes

    def compare_node_shape_constraints(self, ns1, ns2, c):
        """
        Compare constraints in the given two node shapes
        """
        for constraint in self.constriants_check:
            c1 = self.g1.value(ns1, constraint)
            c2 = self.g2.value(ns2, constraint)
            if c1 is None and c2 is None:
                continue
            elif c1 != c2:
                if c1:
                    # self.g1.remove((ns1, constraint, c1))
                    self.in_first_graph.add((ns1, constraint, c1))
                    self.update_infirst_report(ns1, c, constraint, ns2, self.inconsistency_level2)
                if c2:
                    self.g2.remove((ns2, constraint, c2))
                    self.in_second_graph.add((ns2, constraint, c2))
                    self.update_insecond_report(ns2, c, constraint, ns1, self.inconsistency_level2)
                self.rml_validation_report["Conflict"]["Number"] += 1
                self.rml_validation_report["Conflict"]["TriplesMap"][self.getTM(ns2)] = {c: f"RML does not have consistent triples map for this class due to {constraint}"}
            else:
                self.g2.remove((ns2, constraint, c2))
        # Final S1 is in_both graph


    def compare_property_shapes(self, ns1, ns2, ps1, ps2, p, or_mode=False):
        """
        Compare the given two property shapes
        """
        consistency = True
        c1, c2 = {}, {}
        for constraint in self.constriants_check:
            c1[constraint] = self.g1.value(ps1, constraint)
            c2[constraint] = self.g2.value(ps2, constraint)
            
        # Replace the above code with the following code
        node1, node2 = self.g1.value(ps1,SH.node), self.g2.value(ps2,SH.node)
        if node1:
            if self.g1.value(node1, SH.property) is None:
                for constraint in self.constriants_check:
                    if self.g1.value(ps1, constraint): c1[constraint] = self.g1.value(ps1, constraint) 
            else:
                c1[SH.node] = node1
        if node2:
            if self.g2.value(node2, SH.property) is None:
                for constraint in self.constriants_check:
                    if self.g2.value(ps2, constraint): c2[constraint] = self.g2.value(ps2, constraint)
            else:
                c2[SH.node] = node2

        if c1 != c2 and not or_mode:        
            # if c1:
            # self.g1.remove((ns1, URIRef("http://www.w3.org/ns/shacl#property"), ps1))
            self.in_first_graph.add((ns1, URIRef("http://www.w3.org/ns/shacl#property"), ps1))
            # self.g1, self.in_first_graph = move_graph([ps1], g_remove = Graph()+self.g1, g_add = self.in_first_graph)
            _, self.in_first_graph = move_graph([ps1], g_remove = Graph()+self.g1, g_add = self.in_first_graph)
            self.update_infirst_report(ns1, p, c1, ns2, self.inconsistency_level2)
            # if c2:
            self.g2.remove((ns2, URIRef("http://www.w3.org/ns/shacl#property"), ps2))
            self.in_second_graph.add((ns2, URIRef("http://www.w3.org/ns/shacl#property"), ps2))
            self.g2, self.in_second_graph = move_graph([ps2], g_remove = self.g2, g_add = self.in_second_graph)
            self.update_insecond_report(ns2, p, c2, ns1, self.inconsistency_level2)

            # which constraint is not consistent
            error_constraints = []
            for constraint in self.constriants_check:
                if c1[constraint] != c2[constraint]:
                    error_constraints.append(f"{constraint} {c1[constraint]} != {c2[constraint]}")
            self.rml_validation_report["Conflict"]["Number"] += 1
            self.rml_validation_report["Conflict"]["TriplesMap"][self.getTM(ns2)] = {p: f"RML does not have consistent triples map for this property due to: {" ".join(error_constraints)}"}

        elif c1 == c2 and not or_mode:
            # remove the property shape from the second graph
            self.g2.remove((ns2, URIRef("http://www.w3.org/ns/shacl#property"), ps2))
            self.g2, _ = move_graph([ps2], g_remove = self.g2, g_add = Graph())
        elif c1 != c2 and or_mode:
            consistency = False
        return consistency

    def compare_or_shapes(self, or_shapes1, or_shapes2, p):
        or_constraints1, or_constraints1 = [], []
        for or_bn1 in or_shapes1:
            or_constraints1.append(self.g1.value(or_bn1, SH.property))


    def update_infirst_report(self, ns_identifier, class_property, violation_reason, ns_identifier_other, level):
        self.in_first_report.append([ns_identifier, class_property, violation_reason, ns_identifier_other, level])

    def update_insecond_report(self, ns_identifier, class_property, violation_reason, ns_identifier_other, level):
        self.in_second_report.append([ns_identifier, class_property, violation_reason, ns_identifier_other, level])

    def statistics(self):
        classes1, classes2 = set(), set()
        properties1, properties2 = set(), set()
        for s, p, o in self.g1:
            if p == SH.targetClass or p == SH["class"]:
                classes1.add(o)
            elif p == SH.path:
                properties1.add(o)
        for s, p, o in self.g2:
            if p == SH.targetClass or p == SH["class"]:
                classes2.add(o)
            elif p == SH.path:
                properties2.add(o)
        
        print("Number of classes in S1:", len(classes1), "Number of properties in S1:", len(properties1))
        print("Number of classes in S2:", len(classes2), "Number of properties in S2:", len(properties2))
        print(f"S1 has extra {len(classes1 - classes2)} classes than S2")
        print(f"S1 has extra {len(properties1 - properties2)} properties than S2")
        print(f"S2 has extra {len(classes2 - classes1)} classes than S1")
        print(f"S2 has extra {len(properties2 - properties1)} properties than S1")

    
    def getTM(self, ns):
        return str(ns).split("/shape")[0]
    
    def compare(self, g1_path, g2_path):
        """
        Compare two SHACL graphs
        """
        self.g1, self.g2 = Graph().parse(g1_path, format="turtle"), Graph().parse(g2_path, format="turtle")
        self.g1_backup = Graph().parse(g1_path, format="turtle")
        self.statistics()
        print("Start comparing two SHACL graphs...")
        self.index_s2 = self.index_shape_graph()

        for ns1 in self.g1.subjects(RDF.type, URIRef("http://www.w3.org/ns/shacl#NodeShape")):
            target_class1 = self.g1.value(ns1, URIRef("http://www.w3.org/ns/shacl#targetClass"))
            matching_shapes = self.index_s2.get(target_class1)

            if not matching_shapes:
                # If S2 does not have a matching node shape
                # self.g1, self.in_first_graph = move_graph([ns1], g_remove = Graph()+self.g1, g_add = self.in_first_graph)
                _, self.in_first_graph = move_graph([ns1], g_remove = Graph()+self.g1, g_add = self.in_first_graph)
                self.update_infirst_report(ns1, target_class1, None, None, self.inconsistency_level1)
                self.rml_validation_report["Missed"]["Number"] += 1
                self.rml_validation_report["Missed"]["TriplesMap"][str(ns1)] = {target_class1: "RML does not have triples map for this class"}
            else:
                # Compare each node shape in S2 that targets the same class
                for match in matching_shapes:
                    # Go through each matching node shape in S2
                    for ns2, pss2 in match.items():
                        # First compare constraints in the node shape
                        self.compare_node_shape_constraints(ns1, ns2, target_class1)
                        # Then compare property shapes that directly asscoiated with node shape via sh:property
                for ps1 in self.g1.objects(ns1, SH["property"]):
                    foundPS = False
                    p1 = self.g1.value(ps1, SH["path"])

                    for match in matching_shapes:
                        for ns2, pss2 in match.items():
                            ps2 = pss2.get(p1)
                            if ps2:
                                # Compare property shapes contraint
                                foundPS = True
                                self.compare_property_shapes(ns1, ns2, ps1, ps2, p1)
                    if not foundPS and self.g1.value(ns1, SH["property"]):
                        # If S2 does not have a matching property shape
                        # self.g1.remove((ns1, SH["property"], ps1))
                        self.in_first_graph.add((ns1, SH["property"], ps1))
                        # self.g1, self.in_first_graph = move_graph([ps1], g_remove = Graph()+self.g1, g_add = self.in_first_graph)
                        _, self.in_first_graph = move_graph([ps1], g_remove = Graph()+self.g1, g_add = self.in_first_graph)
                        self.update_infirst_report(ns1, p1, None, ns2, self.inconsistency_level1)
                        for match in matching_shapes:
                            for ns2, pss2 in match.items():
                                self.rml_validation_report["Missed"]["Number"] += 1
                                self.rml_validation_report["Missed"]["TriplesMap"][self.getTM(ns2)] = {p1: "RML does not have pom for this property"}

                # Then compare property shapes that associated with node shape via sh:or
                for or_group in self.g1.objects(ns1, SH["or"]):
                    consistencyOr = False
                    if or_group is None:
                        continue
                    for match in matching_shapes:
                        for ns2, pss2 in match.items():
                            if pss2.get(SH["or"]) is None:
                                # S1 has extra property shapes under sh:or
                                # self.g1.remove((ns1, SH["or"], or_group))
                                # self.in_first_graph.add((ns1, SH["or"], or_group))
                                # self.g1, self.in_first_graph = move_graph([or_group], g_remove = Graph()+self.g1, g_add = self.in_first_graph)
                                # self.update_infirst_report(ns1, SH["or"], SH["or"], None, self.inconsistency_level1)

                                # # Get sh:path value in sh:or (sh:property [sh:path])
                                # o = self.g1.value(or_group, RDF.first)
                                # or_ps1 = self.g1.value(o, SH["property"])
                                # p = self.g1.value(or_ps1, SH.path)

                                # self.rml_validation_report["Missed"]["Number"] += 1
                                # self.rml_validation_report["Missed"]["TriplesMap"][ns1] = {p, "RML does not have multiple poms for this property"}
                                continue
                            else:
                                or_shapes1 = self.or_shape(self.g1, or_group, {})
                                or_shapess2 = pss2[SH["or"]]
                                or_p1 = list(or_shapes1.keys())[0]
                                
                                for or_bn2, or_shapes2 in or_shapess2.items():
                                    or_p2 = list(or_shapes2.keys())[0]

                                    if or_p1 == or_p2:
                                        # Compare property shapes under sh:or
                                        orpss1 = or_shapes1[or_p1] # list
                                        orpss2 = or_shapes2[or_p2] # list
                                        for ps1 in orpss1:
                                            for ps2 in orpss2:
                                                consistency = self.compare_property_shapes(ns1, ns2, ps1, ps2, SH["or"], or_mode=True)
                                                if consistency: 
                                                    break
                                            if not consistency:
                                                # S1 has extra property shapes under sh:or
                                                # self.g1.remove((ns1, SH["or"], or_group)) 
                                                self.in_first_graph.add((ns1, SH["or"], or_group))
                                                # self.g1, self.in_first_graph = move_graph([or_group], g_remove = Graph()+self.g1, g_add = self.in_first_graph)
                                                _, self.in_first_graph = move_graph([or_group], g_remove = Graph()+self.g1, g_add = self.in_first_graph)
                                                self.update_infirst_report(ns1, or_p1, SH["or"], None, self.inconsistency_level2)
                                                self.g2.remove((ns2, SH["or"], or_bn2))
                                                self.in_second_graph.add((ns2, SH["or"], or_bn2))
                                                self.g2, self.in_second_graph = move_graph([or_bn2], g_remove = self.g2, g_add = self.in_second_graph)
                                                self.update_insecond_report(ns2, or_p2, SH["or"], None, self.inconsistency_level2)
                                                self.rml_validation_report["Conflict"]["Number"] += 1
                                                self.rml_validation_report["Conflict"]["TriplesMap"][self.getTM(ns2)] = {or_p2: "RML does not have consistent poms for this property"}
                                                break
                                            else:
                                                consistencyOr = True
                                                self.g2.remove((ns2, SH["or"], or_bn2))
                                                self.g2, _ = move_graph([or_bn2], g_remove = self.g2, g_add = self.in_second_graph)
                                
                                if not consistencyOr:
                                    # S2 does not have same property under sh:or

                                    # self.g1.remove((ns1, SH["or"], or_group))
                                    self.in_first_graph.add((ns1, SH["or"], or_group))
                                    # self.g1, self.in_first_graph = move_graph([or_group], g_remove = Graph()+self.g1, g_add = self.in_first_graph)
                                    _, self.in_first_graph = move_graph([or_group], g_remove = Graph()+self.g1, g_add = self.in_first_graph)
                                    self.update_infirst_report(ns1, SH["or"], None, None, self.inconsistency_level2)
                                    # self.g2.remove((ns2, SH["or"], or_bn2))
                                    # self.in_second_graph.add((ns2, SH["or"], or_bn2))
                                    # self.g2, self.in_second_graph = move_graph([or_bn2], g_remove = self.g2, g_add = self.in_second_graph)
                                    # self.update_insecond_report(ns2, SH["or"], None, None, self.inconsistency_level2)

                                    self.rml_validation_report["Missed"]["Number"] += 1
                                    self.rml_validation_report["Missed"]["TriplesMap"][self.getTM(ns2)] = {or_p1: "RML does not have multiple poms for this property"}

        # add validation report for the rest graph in self.g2 which is extra shapes comapred to CM
        for ns2 in self.g2.subjects(RDF.type, URIRef("http://www.w3.org/ns/shacl#NodeShape")):
            target_class2 = self.g2.value(ns2, URIRef("http://www.w3.org/ns/shacl#targetClass"))
            if target_class2:
                self.rml_validation_report["Extra"]["Number"] += 1
                self.rml_validation_report["Extra"]["TriplesMap"][self.getTM(ns2)] = {str(target_class2): "CM does not have triples map for this class"}
            for ps2 in self.g2.subjects(ns2, SH["property"]):
                p2 = self.g2.value(ps2, SH["path"])
                self.rml_validation_report["Extra"]["Number"] += 1
                self.rml_validation_report["Extra"]["TriplesMap"][self.getTM(ns2)] = {p2: "CM does not have pom for this property"}
            for or_group in self.g2.objects(ns2, SH["or"]):
                if or_group is None:
                    continue
                ps = self.g2.value(or_group, RDF.first)
                p = self.g2.value(ps, SH.path)
                self.rml_validation_report["Extra"]["Number"] += 1
                self.rml_validation_report["Extra"]["TriplesMap"][self.getTM(ns2)] = {p: "CM does not have multiple poms for this property"}
        
        
        self.in_both_graph = self.g1 - self.in_first_graph
        self.in_second_graph += self.g2
        # remove node shapes that only has one triple s rdf:type sh:NodeShape
        for ns,_,_ in self.in_second_graph.triples((None, RDF.type, SH.NodeShape)):
            if len(list(self.in_second_graph.triples((ns, None, None)))) == 1:
                self.in_second_graph.remove((ns, RDF.type, SH.NodeShape))
        print("Finished comparing two SHACL graphs")


    def save_results(self, folder_path):
        """
        Save the results to files
        """
        print("Start saving the results ...")
        in_both_file = os.path.join(folder_path, "in_both.ttl")
        in_first_file = os.path.join(folder_path, "in_first.ttl")
        in_second_file = os.path.join(folder_path, "in_second.ttl")
        self.in_both_graph.serialize(in_both_file, format="turtle")
        self.in_first_graph.serialize(in_first_file, format="turtle")
        self.in_second_graph.serialize(in_second_file, format="turtle")

        in_first_report_file = os.path.join(folder_path, "in_first_report.csv")
        self.in_first_report = DataFrame(self.in_first_report, columns=["Shape in S1", "Class/Property", "ViolationReason", "Shape in S2", "Level"])
        self.in_first_report.to_csv(in_first_report_file, index=False)

        in_second_report_file = os.path.join(folder_path, "in_second_report.csv")
        self.in_second_report = DataFrame(self.in_second_report, columns=["Shape in S2", "Class/Property", "ViolationReason", "Shape in S1", "Level"])
        self.in_second_report.to_csv(in_second_report_file, index=False)
        
        rml_validation_report_file = os.path.join(folder_path, "rml_validation_report.json")
        with open(rml_validation_report_file, "w") as f:
            f.write(json.dumps(self.rml_validation_report, indent=4))
        print("Successfully saved the results in the folder:", folder_path)

if __name__ == "__main__":
    # Example usage:
    # g1_path = "mapping_repair/example_CM2SHACL.ttl"
    # g2_path = "mapping_repair/example_RML2SHACL.ttl"
    g1_path = "mapping_repair/dataset/shacl_output_v1.ttl"
    g2_path = "mapping_repair/dataset/rewritten-rml_f03.ttl-output-shape.ttl"

    checker = SHACLConsistencyChecker()
    checker.compare(g1_path, g2_path)

    checker.save_results("mapping_repair/report")
