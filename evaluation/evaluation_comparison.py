import rdflib
from rdflib import Graph, URIRef
import sys
from os import listdir
from os.path import isfile, join

class comparison():
    def __init__(self):
        pass

    def shacl_analysis(self, shacl_path):
        # calculate classes and properties in SHACL shapes
        shacl_graph = Graph()
        for p in shacl_path:
            shacl_graph += Graph().parse(p, format='turtle')
        target_classes, shacl_pathes, shacl_classes = set(), set(), set()
        for s, p, o in shacl_graph:
            if URIRef("http://www.w3.org/ns/shacl#targetClass") == p:
                target_classes.add(o)
            if URIRef("http://www.w3.org/ns/shacl#path") == p:
                shacl_pathes.add(o)
            if URIRef("http://www.w3.org/ns/shacl#class") == p:
                shacl_classes.add(o)
        return target_classes, shacl_pathes, shacl_classes

    def rml_analysis(self, rml_folder):
        # calculate classes and properties in RML mapping
        rml_files = [join(rml_folder, f) for f in listdir(rml_folder) if isfile(join(rml_folder, f))]
        rml_graph = Graph()
        for f in rml_files:
            rml_graph += Graph().parse(f, format='turtle')
        rml_classes, rml_properties = set(), set()
        for s, p, o in rml_graph:
            if URIRef("http://www.w3.org/ns/r2rml#class") == p:
                rml_classes.add(o)
            elif URIRef("http://www.w3.org/ns/r2rml#predicate") == p:
                rml_properties.add(o)
        return rml_classes, rml_properties
        
            

if __name__ == '__main__':
    # shacl_gt_path = ["TED/SHACL/eCatalogue_shacl_shapes.ttl", "TED/SHACL/eCatalogue_shacl_shapes.ttl","TED/SHACL/eOrdering_shacl_shapes.ttl","TED/SHACL/ePO_shacl_shapes.ttl"]
    shacl_gt_path = ["TED/SHACL/ePO_shacl_shapes.ttl"]
    shacl_pd_path = ["shacl_output_v1.ttl"]
    rml_folder = "TED/RML"
    c = comparison()
    target_classes_gt, shacl_pathes_gt, shacl_classes_gt = c.shacl_analysis(shacl_gt_path)
    print(f"SHACL_gt Classes: {len(shacl_classes_gt)}, SHACL_gt Properties: {len(shacl_pathes_gt)}")
    target_classes_pd, shacl_pathes_pd, shacl_classes_pd = c.shacl_analysis(shacl_pd_path)
    print(f"SHACL_pd Classes: {len(shacl_classes_pd)}, SHACL_pd Properties: {len(shacl_pathes_pd)}")
    rml_classes, rml_properties = c.rml_analysis(rml_folder)
    print(f"RML Classes: {len(rml_classes)}, RML Properties: {len(rml_properties)}")

    #print the difference class and properties in SHACL_pd and RML
    print("Classes in SHACL_pd but not in RML:")
    print(len(shacl_classes_pd.difference(rml_classes)))
    print("Classes in RML but not in SHACL_pd:")
    print(len(rml_classes.difference(shacl_classes_pd)))
    print("Properties in SHACL_pd but not in RML:")
    print(len(shacl_pathes_pd.difference(rml_properties)))
    print("Properties in RML but not in SHACL_pd:")
    print(len(rml_properties.difference(shacl_pathes_pd)))

    #print the difference class and properties in SHACL_gt and RML
    print("Classes in SHACL_gt but not in RML:")
    print(len(shacl_classes_gt.difference(rml_classes)))
    print("Classes in RML but not in SHACL_gt:")
    print(len(rml_classes.difference(shacl_classes_gt)))
    print("Properties in SHACL_gt but not in RML:")
    print(len(shacl_pathes_gt.difference(rml_properties)))
    print("Properties in RML but not in SHACL_gt:")
    print(len(rml_properties.difference(shacl_pathes_gt)))

    #print the difference class and properties in SHACL_gt and SHACL_pd
    print("Classes in SHACL_gt but not in SHACL_pd:")
    print(len(shacl_classes_gt.difference(shacl_classes_pd)))
    print("Classes in SHACL_pd but not in SHACL_gt:")
    print(len(shacl_classes_pd.difference(shacl_classes_gt)))
    print("Properties in SHACL_gt but not in SHACL_pd:")
    print(len(shacl_pathes_gt.difference(shacl_pathes_pd)))
    print("Properties in SHACL_pd but not in SHACL_gt:")
    print(len(shacl_pathes_pd.difference(shacl_pathes_gt)))