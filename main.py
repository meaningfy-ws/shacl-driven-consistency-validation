from src.cm2shacl import CMtoSHACL
import argparse
import pyshacl
from rdflib import Graph

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Translate Conceptual Mapping to SHACL')
    parser.add_argument("-cm", "--cm_file",  help='conceptual mapping file location', type=str)
    parser.add_argument("-cf", "--config_file", help='config file location', type=str, default='config.ini')
    parser.add_argument("-cv", "--cm_version", help='conceptual mapping versionin config file', type=str, default='Conceptual Mapping Version 1.0')
    parser.add_argument("-o", "--output_file", help='output file location', type=str, default=None)
    
    parser.add_argument("--validation_shacl", help='shacl shapes used to validate RDF graph', type=str)
    parser.add_argument("--validation_rdf", help='RDF graph to validate', type=str)
    parser.add_argument("--validation_report", help='output file location for validation report', type=str)

    parser.add_argument("--close_shapes", help='close shapes', type=bool, default=False)
    args = parser.parse_args()

    if args.cm_file:
        print("Translating Conceptual Mapping to SHACL shapes")
        C2S = CMtoSHACL()
        C2S.evaluate_file(args)

    if args.validation_rdf:
        print("Validating RDF graph using SHACL shapes")
        data_g = Graph().parse(args.validation_rdf, format='turtle')
        if args.validation_shacl:
            shacl_g = Graph().parse(args.validation_shacl, format='turtle')
        else:
            shacl_g = Graph().parse(args.output_file, format='turtle')
        conforms, results_graph, results_text = pyshacl.validate(data_g, shacl_graph=shacl_g)
        if args.validation_report:
            results_graph.serialize(destination=args.validation_report, format='turtle')
        else:
            results_graph.serialize(destination=args.validation_rdf + 'shacl_validation_report.ttl', format='turtle')