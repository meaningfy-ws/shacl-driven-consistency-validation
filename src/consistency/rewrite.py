import os
import rdflib
from rdflib import Graph
from rdflib.namespace import SH, RDF, RDFS, XSD
from rdflib import Namespace, URIRef, Literal, BNode
from collections import defaultdict
from .rml2shacl.RMLtoShacl import RMLtoSHACL

class SHACLRewrite:
    def __init__(self):
        preserved_constraints_file = "src/consistency/preserved_constraints.txt"
        self.preserved_constraints = self.load_preserved_constraints(preserved_constraints_file)

    def load_preserved_constraints(self, file_path):
        with open(file_path, 'r') as file:
            return [URIRef(line.strip()) for line in file.readlines()]

    def filter_constraints(self, shape_graph):
        """
        only focus on interested constraints, remove others
        """
        for s, p, o in shape_graph.triples((None, None, None)):
            if p not in self.preserved_constraints:
                shape_graph.remove((s, p, o))
        return shape_graph

    def fix_nodeKind(self, shape_graph):
        """
        If node shape has sh:class then sh:nodeKind should be IRI
        """
        for s, p, o in shape_graph.triples((None, SH["class"], None)):
            shape_graph.remove((s, SH.nodeKind, None))
            shape_graph.add((s, SH.nodeKind, SH.IRI))

        for s, p, o in shape_graph.triples((None, RDF.type, SH.NodeShape)):
            shape_graph.remove((s, SH.nodeKind, None))
            shape_graph.add((s, SH.nodeKind, SH.IRI))
        return shape_graph

    def replace_node_with_class(self, shape_graph):
        """
        If property shape has sh:node NS and NS has sh:class C, then the sh:node NS is replaced with sh:class C。
        """
        for s, p, o in shape_graph.triples((None, SH.node, None)):
            class_for_ns = list(shape_graph.objects(o, SH["class"]))
            if class_for_ns:
                shape_graph.remove((s, SH.node, o))
                shape_graph.add((s, SH["class"], class_for_ns[0]))
            """Replace sh:node with corresponding constraints if the node shape does not has property shapes"""
            if not list(shape_graph.triples((o, SH.property, None))):
                nodekind = shape_graph.value(o, SH.nodeKind)
                if nodekind:
                    shape_graph.add((s, SH.nodeKind, nodekind))
                shape_graph.remove((o, None, None))
        return shape_graph

    def combine_shapes_with_same_path(self, graph):
        """
        Specifically designed for SHACL shapes from RML2SHACL
        Combines property shapes under the same node shape that have the same `sh:path` into a single property shape using `sh:or`.
        """
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
                        graph = self.remove_subgraph(ps, graph)
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
                        graph = self.remove_subgraph(ps, graph)
            if path_dict:
                graph = self.addSHACLOR(ns, path_dict, graph)
        return graph

    def remove_subgraph(self, ps, graph):
        """
        Remove duplicate property shapes
        """
        for s, p, o in graph.triples((ps, None, None)):
            graph.remove((s, p, o))
        for s, p, o in graph.triples((None, None, ps)):
            graph.remove((s, p, o))
        return graph
    
    def addSHACLOR(self, ns, path_dict, g):
        # bn_prop = BNode()
        # g.add((ns, SH.property, bn_prop)) 
        # s = bn_prop
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
                # g.add((bn,RDF.first,i))
                nextBn = BNode()
                g.add((bn,RDF.rest,nextBn))
                bn = nextBn
            g.remove((ns, SH.property, property_shapes[-1]))
            bn_prop = BNode()
            g.add((bn, RDF.first, bn_prop))
            g.add((bn_prop, SH.property, property_shapes[-1]))
            
            # g.add((bn,RDF.first,property_shapes[-1]))
            g.add((bn,RDF.rest,RDF.nil))
        return g


    def rml2shacl(self, mapping_path, output_path):
        RtoS = RMLtoSHACL()
        RtoS.evaluate_file(mapping_path, output_path)
    
    def rewrite_shacl(self, rml_path):
        # Check path is folder of file, if folder, then process all files in the folder
        rml_graph = Graph()
        if os.path.isdir(rml_path):
            for file in os.listdir(rml_path):
                if file.endswith(".ttl"):
                    rml_graph.parse(f"{rml_path}/{file}", format="ttl")
        else:
            rml_graph.parse(rml_path, format="ttl")
        # Write RML graph in temp folder
        rml_graph.serialize(destination="temp/rml.ttl", format="ttl")

        # Generate SHACL shapes from RML rules
        self.rml2shacl("temp/rml.ttl", "temp/rml_shacl.ttl")

        shape_graph = rdflib.Graph().parse("temp/rml_shacl.ttl", format="ttl")
        shape_graph = self.filter_constraints(shape_graph)
        shape_graph = self.fix_nodeKind(shape_graph)
        shape_graph = self.replace_node_with_class(shape_graph)
        shape_graph = self.combine_shapes_with_same_path(shape_graph)

        return shape_graph


if __name__ == "__main__":

    rewritter = SHACLRewrite()
    
    rewritten_graph = rewritter.rewrite_shacl("mapping_repair/dataset/rml_f03.ttl-output-shape.ttl")
    
    rewritten_graph.serialize(f"rewritten-rml_f03.ttl-output-shape.ttl", format="ttl")

