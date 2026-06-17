#!/usr/bin/env python3
"""
CM2SHACL fine-grained semantic correctness check: random sampling script.
"""
import re, glob, csv, random

SEED = 42
CHECK_COLS = ["targetClass", "class", "path", "nodeKind", "datatype", "in", "or", "all_correct"]
COLS = ["suite", "cell", "node_shape", "property_path"] + CHECK_COLS

def main():
    files = sorted(glob.glob("evaluation/*/*/cm_shacl.ttl"))
    pool = {}  # (suite, cell) -> {suite, cell, node_shape, property_path}
    for f in files:
        parts = f.split("/")
        suite = parts[1] + "/" + parts[2]
        text = open(f).read()
        blocks = re.split(r'\n(?=\S+ a sh:NodeShape)', text)
        for b in blocks:
            m = re.match(r'(\S+)\s+a sh:NodeShape', b)
            if not m:
                continue
            node_shape = m.group(1)
            head = b.split('sh:property')[0]
            for c in re.findall(r'dcterms:source\s+"([^"]+)"', head):
                pool.setdefault((suite, c), {"suite": suite, "cell": c,
                                             "node_shape": node_shape, "property_path": ""})["node_shape"] = node_shape
            for pm in re.finditer(r'\[(.*?)\]', b, re.DOTALL):
                ps = pm.group(1)
                cells = re.findall(r'dcterms:source\s+"([^"]+)"', ps)
                if not cells:
                    continue
                cell = cells[0]
                pathm = re.search(r'sh:path\s+(\S+?)\s*[\];]', ps)
                path = pathm.group(1) if pathm else ""
                d = pool.setdefault((suite, cell), {"suite": suite, "cell": cell,
                                                    "node_shape": node_shape, "property_path": ""})
                d["node_shape"] = node_shape
                if path:
                    d["property_path"] = path

    sf = sorted([k for k in pool if k[0].startswith("standardForms")])
    ef = sorted([k for k in pool if k[0].startswith("eforms")])
    print(f"Pool: SF={len(sf)} eForms={len(ef)} total={len(pool)}")

    random.seed(SEED)
    sample_keys = random.sample(sf, 50) + random.sample(ef, 50)

    with open("cm2shacl_sampling_correctness_check.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for k in sample_keys:
            d = pool[k]
            row = {"suite": d["suite"], "cell": d["cell"],
                   "node_shape": d["node_shape"], "property_path": d["property_path"]}
            for c in CHECK_COLS:
                row[c] = ""   # left empty for manual checking
            w.writerow(row)

    print(f"Wrote cm2shacl_sampling_correctness_check.csv with {len(sample_keys)} sampled rules.")

if __name__ == "__main__":
    main()
