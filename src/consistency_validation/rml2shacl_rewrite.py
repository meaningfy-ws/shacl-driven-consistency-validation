import os
import rdflib
from rdflib import Graph
from rdflib.namespace import SH, RDF, RDFS, XSD
from rdflib import Namespace, URIRef, Literal, BNode
from collections import defaultdict
from rdflib.collection import Collection
from .rml2shacl.RMLtoShacl import RMLtoSHACL
import argparse

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
            
            graph.remove((ns, SH.property, ps))

        # Add refined property shapes
        for path, shapes in path_dict.items():
            if len(shapes) == 1:
                graph.add((ns, SH.property, shapes[0]))
                for src in dctsource_dict[shapes[0]]:
                    graph.add((shapes[0], dctsource, src))
                continue
            graph.remove((ps, SH.path, path))
            # Merge sh:in values
            in_values = set()
            nodeKinds = set()
            dataTypes = set()
            classes = set()
            nodes = set()
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
                for o in graph.objects(ps, SH["node"]):
                    nodes.add(o)
                    graph.remove((ps, SH["node"], o))

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
            add_or_shape(SH.node, nodes)

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

class RML2SHACLRewrite:
    def __init__(self):
        preserved_constraints_file = "src/consistency_validation/preserved_constraints.txt"
        self.preserved_constraints = self.load_preserved_constraints(preserved_constraints_file)
        self.dctsource = URIRef("http://purl.org/dc/terms/source")

    def load_preserved_constraints(self, file_path):
        with open(file_path, 'r') as file:
            return [URIRef(line.strip()) for line in file.readlines()]

    def addSources(self, graph):
        """
        Add dct:source to the SHACL shapes to keep track of the original RML rules
        """
        for s, p, o in graph.triples((None, RDF.type, SH.NodeShape)):
            source = URIRef(str(s).split("/shape")[0])
            graph.add((s, self.dctsource, source))
            for _, _, o2 in graph.triples((s, SH.property, None)):
                graph.add((o2, self.dctsource, source))
        return graph
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
        shape_graph.bind("dcterms", URIRef("http://purl.org/dc/terms/"))
        shape_graph = self.addSources(shape_graph)
        shape_graph = self.filter_constraints(shape_graph)
        shape_graph = self.fix_nodeKind(shape_graph)
        shape_graph = self.replace_node_with_class(shape_graph)
        shape_graph = combine_shapes_with_same_path(shape_graph)

        shape_graph.remove((None, SH.datatype, XSD.anyURI))

        return shape_graph


if __name__ == "__main__":
    
    # Argparse for command line arguments
    parser = argparse.ArgumentParser(description='RML to SHACL rewrite')
    parser.add_argument("-rml", "--rml_file", help='RML file location', type=str)
    parser.add_argument("-o", "--output_file", help='output file location', type=str, default="temp/rml_shacl_rewrite.ttl")
    args = parser.parse_args()

    rewritter = RML2SHACLRewrite()
    rewritter_graph = rewritter.rewrite_shacl(args.rml_file)
    rewritter_graph.serialize(destination=args.output_file, format="ttl")
    print(f"Generated and rewritten SHACL shapes saved to: {args.output_file}")
    
    # rewritten_graph = rewritter.rewrite_shacl("mapping_repair/dataset/rml_f03.ttl-output-shape.ttl")
    
    # rewritten_graph.serialize(f"rewritten-rml_f03.ttl-output-shape.ttl", format="ttl")


