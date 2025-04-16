from rdflib import Graph, URIRef
import pyshacl

rdf_graph_path = "evaluation/package_F03/rdf/form_number_F03_2021/000163-2021/000163-2021.ttl"
rdf_g = Graph().parse(rdf_graph_path, format='turtle')

shacl_graph_cm2shacl_path = "shacl_output_v1.ttl"
shacl_cm2shacl_g = Graph().parse(shacl_graph_cm2shacl_path, format='turtle')

shacl_graph_ted_path = "TED/SHACL/ePO_shacl_shapes.ttl"
shacl_ted_g = Graph().parse(shacl_graph_ted_path, format='turtle')

conforms, results_graph, results_text = pyshacl.validate(rdf_g, shacl_graph=shacl_cm2shacl_g)
results_graph.serialize(destination="validation_report_cml2shacl.ttl", format='turtle')

conforms, results_graph, results_text = pyshacl.validate(rdf_g, shacl_graph=shacl_ted_g)
results_graph.serialize(destination="validation_report_ted.ttl", format='turtle')

