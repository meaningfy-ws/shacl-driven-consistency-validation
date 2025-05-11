import os
import argparse
import json
import glob
import logging
from src.cm2shacl.cm2shacl import CMtoSHACL
from src.consistency_validation.rml2shacl_rewrite import RML2SHACLRewrite
from src.consistency_validation.owl2shacl_rewrite import enhance_shacl_with_owl
from src.consistency_validation.consistency_validation import consistencyValidator
import time


# def setup_logger(log_file="validation.log"):
#     logging.basicConfig(
#         filename=log_file,
#         filemode="w",
#         format="%(asctime)s - %(levelname)s - %(message)s",
#         level=logging.INFO
#     )
#     # 也输出到控制台
#     console = logging.StreamHandler()
#     console.setLevel(logging.INFO)
#     formatter = logging.Formatter("%(message)s")
#     console.setFormatter(formatter)
#     logging.getLogger().addHandler(console)

def run_consistency_validation(args,times):
    os.makedirs("temp", exist_ok=True)
    generated_files = {}

    if args.cm_file:
        print("[CM] Converting CM to SHACL...")
        args.cm_output = args.cm_shacl_file or "temp/cm_shacl.ttl"
        cm_args = argparse.Namespace(
            cm_file=args.cm_file,
            config_file=args.config_file,
            cm_version=args.cm_version,
            output_file=args.cm_output,
            close_shapes=False,
        )
        C2S = CMtoSHACL()
        C2S.evaluate_file(cm_args)
        generated_files["CM"] = args.cm_shacl_file
    elif args.cm_shacl_file:
        generated_files["CM"] = args.cm_shacl_file

    if args.rml_file:
        print("[RML] Rewriting SHACL from RML...")
        # rml2shacl = RML2SHACLRewrite()
        # rewritter_graph = rml2shacl.rewrite_shacl(args.rml_file)
        # rewritter_graph.serialize(destination=args.rml_shacl_file, format="ttl")
        generated_files["RML"] = args.rml_shacl_file
    elif args.rml_shacl_file:
        generated_files["RML"] = args.rml_shacl_file

    if args.owl_shacl_rewrite_file:
        generated_files["OWL"] = args.owl_shacl_rewrite_file

    print("[Validation] Running consistency validation...")
    source_files = {"CM": generated_files.get("CM"), "RML": generated_files.get("RML"), "OWL": generated_files.get("OWL")}
    print("Loading source files for validation...")
    
    print("Starting consistency validation...")
    start_time = time.time()
    validator = consistencyValidator()
    report = validator.validate(source_files, args.owl_cache)
    end_time = time.time()
    print(f"[INFO] Consistency validation took {end_time - start_time:.2f} seconds")
    times.append(end_time - start_time)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[Output] Consistency report saved to: {args.output}")

    return times

def evaluate_all():
    base_dirs = [
        ("standardForms", "Conceptual Mapping Version 1.0"),
        # ("eforms", "eForms 1.0")
    ]

    for base, cm_version in base_dirs:
        suite_paths = glob.glob(f"data/{base}/package_*")
        print("[OWL] Rewriting OWL SHACL with inferred domain/range/subclass info...")
        owl_path = f"data/{base}/ontology/ontology.ttl"
        owl_shacl_path = f"data/{base}/owl2shacl/shacl_ontology.ttl"
        owl_shacl_rewrite_path = f"evaluation/{base}/ontology/shacl_ontology.ttl"
        owl_cache_path = f"evaluation/{base}/ontology/cache.pkl"
        # enhance_shacl_with_owl(shacl_path=owl_shacl_path, owl_path=owl_path, output_path=owl_shacl_rewrite_path)
        times = []
        for suite in suite_paths:
            suite_name = os.path.basename(suite)
            print(f"[INFO] Evaluating suite: {suite_name}")

            cm_file = os.path.join(suite, "transformation/conceptual_mappings.xlsx")
            rml_path = os.path.join(suite, "transformation/mappings")
            

            output_dir = os.path.join("evaluation", base, suite_name)
            os.makedirs(output_dir, exist_ok=True)

            args = argparse.Namespace(
                cm_file=cm_file,
                cm_version=cm_version,
                config_file="config.ini",
                cm_shacl_file=os.path.join(output_dir, "cm_shacl.ttl"),
                rml_file=rml_path,
                rml_shacl_file=os.path.join(output_dir, "rml_shacl.ttl"),
                owl_shacl_rewrite_file=owl_shacl_rewrite_path,
                # owl_cache=owl_cache_path,
                owl_cache = None,
                output=os.path.join(output_dir, "report.json")
            )
            times = run_consistency_validation(args, times)
        print(f"[INFO] Evaluation completed for {base} {len(times)} files.")
        print(f"[INFO] Average time taken for loading source files: {sum(times)/len(times):.2f} seconds")

def main():
    parser = argparse.ArgumentParser(description="Consistency Validation Tool")
    parser.add_argument("mode", choices=["run", "eval"], default="run", help="Mode of operation: 'run' for validation, 'eval' for evaluation")
    parser.add_argument("--cm_file", help="CM Excel file (.xlsx)")
    parser.add_argument("--cm_version", help="CM version in config file",default="Conceptual Mapping Version 1.0")
    parser.add_argument("--config_file", help="Config file location", default="config.ini")
    parser.add_argument("--cm_shacl_file", help="SHACL file generated from CM")
    parser.add_argument("--rml_file", help="RML file or folder")
    parser.add_argument("--rml_output", help="Output path for RML SHACL file")
    parser.add_argument("--rml_shacl_file", help="SHACL file generated from RML")
    parser.add_argument("--owl_file", help="OWL ontology (.ttl or .owl)")
    parser.add_argument("--owl_shacl_file", help="SHACL file generated from OWL")
    parser.add_argument("--owl_shacl_rewrite_file", help="SHACL file generated from OWL")
    parser.add_argument("--owl_cache", help="Cache file for OWL SHACL")
    parser.add_argument("--output", help="Path to output JSON report", default="report.json")

    args = parser.parse_args()

    if args.mode == "run":
        run_consistency_validation(args,[])
    elif args.mode == "eval":
        print("Evaluation mode selected.")
        evaluate_all()

if __name__ == "__main__":
    main()
