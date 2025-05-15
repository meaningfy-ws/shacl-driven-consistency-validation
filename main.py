import os
import argparse
import json
import glob
from src.cm2shacl.cm2shacl import CMtoSHACL
from src.consistency_validation.rml2shacl_rewrite import RML2SHACLRewrite
from src.consistency_validation.owl2shacl_rewrite import enhance_shacl_with_owl
from src.consistency_validation.consistency_validation import consistencyValidator
from src.consistency_validation.owl2shacl.owl2shacl import translateFromFile
import time


def run_consistency_validation(args):
    os.makedirs("temp", exist_ok=True)
    generated_files = {}

    if args.cm:
        print("[CM] Converting CM to SHACL...")
        cm_args = argparse.Namespace(
            cm_file=args.cm,
            config_file=args.config_file,
            cm_version=args.cm_version,
            output_file=args.cm_shacl,
            close_shapes=False, 
        )
        C2S = CMtoSHACL()
        C2S.evaluate_file(cm_args)
        generated_files["CM"] = args.cm_shacl
    elif args.cm_shacl:
        generated_files["CM"] = args.cm_shacl

    if args.rml:
        print("[RML] Generating and Rewriting SHACL from RML...")
        rml2shacl = RML2SHACLRewrite()
        rewritter_graph = rml2shacl.rewrite_shacl(args.rml)
        rewritter_graph.serialize(destination=args.rml_shacl, format="ttl")
        generated_files["RML"] = args.rml_shacl
    elif args.rml_shacl:
        generated_files["RML"] = args.rml_shacl

    if args.owl_cache:
        print("[OWL] Reuse OWL cache...")
    elif args.owl and args.owl_shacl:
        print("[OWL] Generating and Rewriting SHACL from OWL...")
        translateFromFile(args.owl, args.owl_shacl)
        enhance_shacl_with_owl(shacl_path=args.owl_shacl, owl_path=args.owl, output_path=args.owl_shacl+"_rewrite.ttl")
        generated_files["OWL"] = args.owl_shacl+"_rewrite.ttl"
    elif args.owl_shacl:
        generated_files["OWL"] = args.owl_shacl+"_rewrite.ttl"

    print("[Validation] Running consistency validation...")
    source_files = {"CM": generated_files.get("CM"), "RML": generated_files.get("RML"), "OWL": generated_files.get("OWL")}
    
    print("Starting consistency validation...")
    validator = consistencyValidator()
    report = validator.validate(source_files, args.owl_cache)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[Output] Consistency report saved to: {args.output}")



def main():
    parser = argparse.ArgumentParser(description="SHACL-driven Consistency Validation")

    # CM-related arguments
    parser.add_argument("-c", "--cm", help="Conceptual Mapping (CM) Excel file (.xlsx)")
    parser.add_argument("-v", "--cm_version", help="CM version as specified in the config file", default="Conceptual Mapping Version 1.0")
    parser.add_argument("-f", "--config_file", help="ath to configuration file (default: config.ini)", default="config.ini")
    parser.add_argument("-cs", "--cm_shacl", help="Path to SHACL shapes from CM. If not available, specify a target path to generate and store them.", default="temp/cm_shacl.ttl")

    # RML-related arguments
    parser.add_argument("-r", "--rml", help="RML file or folder path")
    parser.add_argument("-rs", "--rml_shacl", help="Path to SHACL shapes from RML. If not available, specify a target path to generate and store them.", default="temp/rml_shacl.ttl")

    # OWL-related arguments
    parser.add_argument("-w", "--owl", help="OWL ontology file (.ttl or .owl)")
    parser.add_argument("-ws", "--owl_shacl", help="Path to SHACL shapes from OWL. If not available, specify a target path to generate and store them.", default="temp/owl_shacl.ttl")
    parser.add_argument("-wc", "--owl_cache", help="Path to existing OWL SHACL cache file (if available)")

    # Output
    parser.add_argument("-o", "--output", help="Path to output JSON consistency validation report", default="report.json")

    args = parser.parse_args()

    run_consistency_validation(args)

    # remove temp folder
    if os.path.exists("temp"):
        for file in glob.glob("temp/*"):
            os.remove(file)
        os.rmdir("temp")
        print("[INFO] Temporary files removed.")
if __name__ == "__main__":
    main()
