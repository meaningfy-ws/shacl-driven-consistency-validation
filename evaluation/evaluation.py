import os
import argparse
import json
import glob
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from cm2shacl.cm2shacl import CMtoSHACL
from consistency_validation.rml2shacl_rewrite import RML2SHACLRewrite
from consistency_validation.owl2shacl_rewrite import enhance_shacl_with_owl
from consistency_validation.consistency_validation import consistencyValidator
import time
from collections import defaultdict
import csv

def load_report(report_path):
    with open(report_path, 'r') as f:
        return json.load(f)

# def analyze_entry(entry):
#     type_key = entry["type"]
#     key_map = {
#         "TCI": "focusNodeDiffer",
#         "PPI": "propertyValueDiffer",
#         "VCI": "constraintDiffer"
#     }
#     result = defaultdict(int)
#     items = entry.get(key_map[type_key], [])
#     result[f"{type_key}_total"] = len(items)
#     for i in items:
#         present = set(i.get("presentIn", {}).keys())   
#         if present == {"CM"}:
#             result[f"{type_key}_CM-RML-OWL"] += 1
#         elif present == {"RML"}:
#             result[f"{type_key}_RML-CM-OWL"] += 1
#         elif present == {"CM", "RML"}:
#             result[f"{type_key}_CM+RML-OWL"] += 1
#         elif present == {"RML", "OWL"}:
#             result[f"{type_key}_RML+OWL-CM"] += 1
#         elif present == {"CM", "OWL"}:
#             result[f"{type_key}_CM+OWL-RML"] += 1
#         # result[f"{type_key}_total"] += 1
#     return result

from collections import defaultdict

def analyze_entry(entry):
    type_key = entry["type"]
    result = defaultdict(int)
    
    items = entry.get("differ", [])
    result[f"{type_key}_total"] = len(items)

    for i in items:
        present = set(i.get("presentIn", {}).keys())

        if present == {"CM"}:
            result[f"{type_key}_Only_CM_missing_RML_OWL"] += 1
        elif present == {"RML"}:
            result[f"{type_key}_Only_RML_missing_CM_OWL"] += 1
        elif present == {"OWL"}:
            result[f"{type_key}_Only_OWL_missing_CM_RML"] += 1
        elif present == {"CM", "RML"}:
            result[f"{type_key}_CM_and_RML_missing_OWL"] += 1
        elif present == {"RML", "OWL"}:
            result[f"{type_key}_RML_and_OWL_missing_CM"] += 1
        elif present == {"CM", "OWL"}:
            result[f"{type_key}_CM_and_OWL_missing_RML"] += 1
        elif present == {"CM", "RML", "OWL"}:
            result[f"{type_key}_Present_in_all_CM_RML_OWL"] += 1
        else:
            result[f"{type_key}_Unknown_case"] += 1

    return result


def analyze_reports(base_dirs):
    rows = []
    for base_dir in base_dirs:
        source_label = os.path.basename(base_dir)
        for pkg in sorted(os.listdir(base_dir)):
            report_file = os.path.join(base_dir, pkg, "report.json")
            if not os.path.exists(report_file):
                continue
            report = load_report(report_file)
            counts = defaultdict(int)
            for entry in report:
                for k, v in analyze_entry(entry).items():
                    counts[k] += v
            counts["source"] = source_label
            counts["package"] = pkg
            rows.append(counts)
    return rows

def write_report(rows, output_file):
    # keys = [
    #     "source", "package",
    #     "TCI_total", "TCI_CM-RML-OWL", "TCI_RML-CM-OWL", "TCI_CM+RML-OWL", "TCI_CM+OWL-RML", "TCI_RML+OWL-CM",
    #     "PPI_total", "PPI_CM-RML-OWL", "PPI_RML-CM-OWL", "PPI_CM+RML-OWL", "PPI_CM+OWL-RML", "PPI_RML+OWL-CM",
    #     "VCI_total", "VCI_CM-RML-OWL", "VCI_RML-CM-OWL", "VCI_CM+RML-OWL" , "VCI_CM+OWL-RML", "VCI_RML+OWL-CM",
    # ]
    keys = [
        "source", "package",
        "TCI_total", "TCI_Only_CM_missing_RML_OWL", "TCI_Only_RML_missing_CM_OWL", "TCI_Only_OWL_missing_CM_RML",
        "TCI_CM_and_RML_missing_OWL", "TCI_CM_and_OWL_missing_RML", "TCI_RML_and_OWL_missing_CM",
        
        "PPI_total", "PPI_Only_CM_missing_RML_OWL", "PPI_Only_RML_missing_CM_OWL", "PPI_Only_OWL_missing_CM_RML",
        "PPI_CM_and_RML_missing_OWL", "PPI_CM_and_OWL_missing_RML", "PPI_RML_and_OWL_missing_CM",
        
        "VCI_total", "VCI_Only_CM_missing_RML_OWL", "VCI_Only_RML_missing_CM_OWL", "VCI_Only_OWL_missing_CM_RML",
        "VCI_CM_and_RML_missing_OWL", "VCI_CM_and_OWL_missing_RML", "VCI_RML_and_OWL_missing_CM",
    ]

    for row in rows:
        for k in keys:
            row.setdefault(k, 0)

    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

        # average of standardForms and eforms

        #calculate averages if standardForms
        avg = {"source": "standardForms", "package": "Average"}
        n = 0
        for row in rows:
            if row["source"] == "standardForms":
                n += 1
                for k in keys[2:]:
                    avg[k] = avg.get(k, 0) + row[k]
        if n > 0:
            for k in keys[2:]:
                avg[k] = round(avg[k] / n, 2)
            writer.writerow(avg)
        #calculate averages if eforms
        avg = {"source": "eforms", "package": "Average"}
        n = 0
        for row in rows:
            if row["source"] == "eforms":
                n += 1
                for k in keys[2:]:
                    avg[k] = avg.get(k, 0) + row[k]
        if n > 0:
            for k in keys[2:]:
                avg[k] = round(avg[k] / n, 2)
            writer.writerow(avg)

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
        rml2shacl = RML2SHACLRewrite()
        rewritter_graph = rml2shacl.rewrite_shacl(args.rml_file)
        rewritter_graph.serialize(destination=args.rml_shacl_file, format="ttl")
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

def evaluate_all(cache=None):
    base_dirs = [
        ("standardForms", "Conceptual Mapping Version 1.0"),
        ("eforms", "eForms 1.0")
    ]

    for base, cm_version in base_dirs:
        suite_paths = glob.glob(f"data/{base}/package_*")
        # print("[OWL] Rewriting OWL SHACL with inferred domain/range/subclass info...")
        owl_path = f"data/{base}/ontology/ontology.ttl"
        owl_shacl_path = f"data/{base}/owl2shacl/shacl_ontology.ttl"
        owl_shacl_rewrite_path = f"evaluation/{base}/ontology/shacl_ontology.ttl"
        if cache == True:
            cache_path = f"evaluation/{base}/ontology/cache.pkl"
        else:
            cache_path = None
        # enhance_shacl_with_owl(shacl_path=owl_shacl_path, owl_path=owl_path, output_path=owl_shacl_rewrite_path)
        times = []
        for suite in suite_paths:
            suite_name = os.path.basename(suite)
            print(f"[INFO] Evaluating suite: {suite_name}")

            # cm_file = os.path.join(suite, "transformation/conceptual_mappings.xlsx")
            # rml_path = os.path.join(suite, "transformation/mappings")
            

            output_dir = os.path.join("evaluation", base, suite_name)
            os.makedirs(output_dir, exist_ok=True)

            args = argparse.Namespace(
                cm_file=None,
                cm_version=cm_version,
                config_file="config.ini",
                cm_shacl_file=os.path.join(output_dir, "cm_shacl.ttl"),
                rml_file=None,
                rml_shacl_file=os.path.join(output_dir, "rml_shacl.ttl"),
                owl_file=None,
                owl_shacl_rewrite_file=owl_shacl_rewrite_path,
                owl_cache=cache_path,
                output=os.path.join(output_dir, "report.json")
            )
            times = run_consistency_validation(args, times)
        print(f"[INFO] Evaluation completed for {base} {len(times)} files.")
        print(f"[INFO] Average time taken for loading source files: {sum(times)/len(times):.2f} seconds")

if __name__ == "__main__":
    # print("[INFO] Starting evaluation without cache...")
    # evaluate_all()
    print("[INFO] Evaluation completed without cache.")
    evaluate_all(cache=True)

    base_dirs = ["evaluation/standardForms", "evaluation/eforms"]
    results = analyze_reports(base_dirs)
    write_report(results, "evaluation/report_analysis.csv")
    print("Report saved to evaluation/report_analysis.csv")
