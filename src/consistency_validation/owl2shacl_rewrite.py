from rdflib import Graph, Namespace, RDF, RDFS, OWL, BNode, URIRef
from rdflib.collection import Collection
from typing import Dict, Set
from collections import defaultdict, deque

SH = Namespace("http://www.w3.org/ns/shacl#")

class OntologyReasoner:
    def __init__(self, graph: Graph):
        self.g = graph
        self.subclass_closure_map = self._build_subclass_closure()
        self.domain_map = self._build_property_map(RDFS.domain)
        self.range_map = self._build_property_map(RDFS.range)

    def _build_subclass_closure(self) -> Dict[URIRef, Set[URIRef]]:
        direct_subclasses = defaultdict(set)
        for subclass, _, superclass in self.g.triples((None, RDFS.subClassOf, None)):
            direct_subclasses[superclass].add(subclass)

        # Compute transitive closure
        closure_map = defaultdict(set)

        def get_all_subclasses(cls):
            visited = set()
            queue = deque([cls])
            while queue:
                current = queue.popleft()
                for child in direct_subclasses.get(current, set()):
                    if child not in visited:
                        visited.add(child)
                        queue.append(child)
            return visited

        for cls in direct_subclasses:
            closure_map[cls] = get_all_subclasses(cls)
        return closure_map

    def _build_property_map(self, predicate: URIRef) -> Dict[URIRef, Set[URIRef]]:
        prop_map = {}
        for prop in set(self.g.subjects(predicate=predicate)):
            prop_map[prop] = set()
            for obj in self.g.objects(prop, predicate):
                if (obj, RDF.type, OWL.Class) in self.g:
                    union = next(self.g.objects(obj, OWL.unionOf), None)
                    if union:
                        collection = Collection(self.g, union)
                        prop_map[prop].update(collection)
                    else:
                        prop_map[prop].add(obj)
        return prop_map

    def get_subclasses(self, cls: URIRef) -> Set[URIRef]:
        return self.subclass_closure_map.get(cls, set())

    def get_property_domain(self, prop: URIRef) -> Set[URIRef]:
        return self.domain_map.get(prop, set())

    def get_property_range(self, prop: URIRef) -> Set[URIRef]:
        return self.range_map.get(prop, set())


def enhance_shacl_with_owl(shacl_path, owl_path, output_path):
    g = Graph()
    g.parse(shacl_path, format="turtle")
    owl_g = Graph().parse(owl_path, format="turtle")

    reasoner = OntologyReasoner(owl_g)

    # Step 1: 移除 sh:or 中仅包含一个元素的情况
    to_remove = []
    to_add = []
    for ps,_,_ in g:
        for or_list in g.objects(ps, SH["or"]):
            collection = Collection(g, or_list)
            if len(collection) == 1:
                inner_node = collection[0]
                for p, o in g.predicate_objects(inner_node):
                    to_add.append((ps, p, o))
                    collection = Collection(g, o)
                    for item in collection:
                        pass  # Just to initialize the collection
                    collection.clear()
                    g.remove((ps, SH["or"], o))
    #             to_remove.append((ps, SH["or"], or_list))
    # for t in to_remove:
    #     g.remove(t)
    # for t in to_add:
    #     g.add(t)

    # Step 2: 基于 path 添加对应的 targetClass（来自 domain）
    for ps, _, p in g.triples((None, SH.path, None)):
        for domain_cls in reasoner.get_property_domain(p):
            g.add((ps, SH.targetClass, domain_cls))

    # Step 3: 对 NodeShape 的 targetClass 扩展其所有子类
    for ns, _, cls in g.triples((None, SH.targetClass, None)):
        for subcls in reasoner.get_subclasses(cls):
            g.add((ns, SH.targetClass, subcls))

    # Step 4: 对 PropertyShape 的 sh:class 扩展其所有子类
    new_ps_triples = []
    for ps in g.subjects(SH.path, None):
        for cls in list(g.objects(ps, SH["class"])):
            for subcls in reasoner.get_subclasses(cls):
                new_ps = BNode()
                for p, o in g.predicate_objects(ps):
                    if p == SH["class"]:
                        new_ps_triples.append((new_ps, p, subcls))
                    else:
                        new_ps_triples.append((new_ps, p, o))
                new_ps_triples.append((new_ps, RDF.type, SH.PropertyShape))
    for t in new_ps_triples:
        g.add(t)

    #step 6: rewrite nodekind
    for ps, _, nk in g.triples((None, SH.datatype, RDFS.Literal)):
        g.remove((ps, SH.datatype, RDFS.Literal))
        g.add((ps, SH.nodeKind, SH.Literal))

    # #step 6: rewrite datattype
    for ps, _, nk in g.triples((None, SH.nodeKind, None)):
        if nk == SH.BlankNodeOrIRI:
            g.remove((ps, SH.nodeKind, nk))
            g.add((ps, SH.nodeKind, SH.IRI))
        # elif nk == SH.IRIOrLiteral:
        #     g.remove((ps, SH.nodeKind, nk))
        #     g.add((ps, SH.nodeKind, SH.Literal))
    
    for s, _, _ in g.triples((None, SH["class"], None)):
        g.add((s, SH.nodeKind, SH.IRI))
    # Step 5: 输出
    g.serialize(destination=output_path, format="turtle")
    print(f"Enhanced SHACL written to {output_path}")

if __name__ == "__main__":
    enhance_shacl_with_owl(
        shacl_path="data/standardForms/owl2shacl/shacl_ePO.ttl",
        owl_path="data/standardForms/ontology/ePO.ttl",
        output_path="evaluation/standardForms/ontology/shacl_ePO_rewrite.ttl"
    )
