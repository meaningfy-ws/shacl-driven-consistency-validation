import os
import json
import csv
from collections import defaultdict

def load_report(report_path):
    with open(report_path, 'r') as f:
        return json.load(f)

def analyze_entry(entry):
    type_key = entry["type"]
    key_map = {
        "FNI": "focusNodeDiffer",
        "PVI": "propertyValueDiffer",
        "PVCI": "constraintDiffer"
    }
    result = defaultdict(int)
    items = entry.get(key_map[type_key], [])
    result[f"{type_key}_total"] = len(items)
    for i in items:
        present = set(i.get("presentIn", {}).keys())   
        if present == {"CM"}:
            result[f"{type_key}_CM-RML-OWL"] += 1
        elif present == {"RML"}:
            result[f"{type_key}_RML-CM-OWL"] += 1
        elif present == {"CM", "RML"}:
            result[f"{type_key}_CM+RML-OWL"] += 1
        elif present == {"RML", "OWL"}:
            result[f"{type_key}_RML+OWL-CM"] += 1
        elif present == {"CM", "OWL"}:
            result[f"{type_key}_CM+OWL-RML"] += 1
        # result[f"{type_key}_total"] += 1
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
    keys = [
        "source", "package",
        "FNI_total", "FNI_CM-RML-OWL", "FNI_RML-CM-OWL", "FNI_CM+RML-OWL", "FNI_CM+OWL-RML", "FNI_RML+OWL-CM",
        "PVI_total", "PVI_CM-RML-OWL", "PVI_RML-CM-OWL", "PVI_CM+RML-OWL", "PVI_CM+OWL-RML", "PVI_RML+OWL-CM",
        "PVCI_total", "PVCI_CM-RML-OWL", "PVCI_RML-CM-OWL", "PVCI_CM+RML-OWL" , "PVCI_CM+OWL-RML", "PVCI_RML+OWL-CM",
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

if __name__ == "__main__":
    base_dirs = ["evaluation/standardForms", "evaluation/eforms"]
    results = analyze_reports(base_dirs)
    write_report(results, "evaluation/report_analysis.csv")
    print("Report saved to evaluation/report_analysis.csv")
