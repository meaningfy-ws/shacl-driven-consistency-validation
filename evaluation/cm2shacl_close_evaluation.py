import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import time
import glob
import csv
import rdflib
import argparse
from pyshacl import validate
from rdflib.namespace import RDF, SH
from rdflib import URIRef
from rdflib import Graph, Namespace, BNode
import re
from cm2shacl.cm2shacl import CMtoSHACL
from cm2shacl.data_load import dataLoader
from cm2shacl.utils import json_load

RR = rdflib.Namespace("http://www.w3.org/ns/r2rml#")
vocab = json_load("src/vocabulary/default_vocabulary_prefixes.json")
vocab_exceptions = ["at-voc"]


ignore_list = ["http://www.w3.org/1999/02/22-rdf-syntax-ns#langString",
               "http://www.w3.org/1999/02/22-rdf-syntax-ns#PlainLiteral",
               "http://www.w3.org/1999/02/22-rdf-syntax-ns#plainLiteral",
                "http://www.w3.org/2001/XMLSchema#dateTime",
"http://www.w3.org/2001/XMLSchema#anyURI",
"http://www.w3.org/2001/XMLSchema#boolean",
"http://www.w3.org/2001/XMLSchema#date",
"http://www.w3.org/2001/XMLSchema#decimal",
"http://www.w3.org/2001/XMLSchema#integer",
"http://www.w3.org/2001/XMLSchema#string",
"http://www.w3.org/2006/time#TemporalUnit",
"http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
"http://www.w3.org/2006/time#numericDuration",
"http://www.w3.org/2006/time#unitDay",
"http://www.w3.org/2006/time#unitMonth",
"http://www.w3.org/2006/time#unitType",
"http://www.w3.org/2006/time#unitWeek",
"http://www.w3.org/2006/time#unitYear",
"None",
"?value",
"true",
"false"]

extra_class = []

def split_string_preserve_url(input_string):
    urls = re.findall(r'<[^>]+>', input_string)

    for i, url in enumerate(urls):
        input_string = input_string.replace(url, f'URL_PLACEHOLDER_{i}')

    parts = input_string.split('/')
    

    for i, part in enumerate(parts):
        if f'URL_PLACEHOLDER_' in part:
            parts[i] = parts[i].replace(f"URL_PLACEHOLDER_{part.split('_')[-1]}", urls[int(part.split('_')[-1])])
        
    return parts

def wordToURL(word):
    word = word.strip()
    if word == "?value" or word == "true" or word == "false":
        return word
    
    # elif word.startswith("<") and (re.match(r'https?://', word[1:-1]) or re.match(r'http?://', word[1:-1])): #TODO: ASK FOR THIS TYPO
    elif word.startswith("<"):
        return URIRef(word[1:-1])

    elif word == "a":
        return RDF.type

    elif ":" in word:
        word = word.split(":")
        if word[0] in vocab:
            return URIRef(vocab[word[0]] + word[1])
        elif word[0] in vocab_exceptions:
            return None
        else:
            raise Exception(f"Prefix {word[0]} not found in the vocabulary")
    else:
        raise Exception(f"Term {word} is not a URL or a prefix")

def controlledClassReplace(c, list_type, XPath,controlled_list_c1,controlled_list_c2):
    
    if list_type == "CL1":
        class_XPath_fragment = XPath.split("/")[1]
        c = controlled_list_c1.get(class_XPath_fragment, c)
    elif list_type == "CL2":
        class_XPath_fragment = XPath.split("/")[-1]
        c = controlled_list_c2.get(class_XPath_fragment, c)
    return c 

def parseClassPath(class_path, XPath,controlled_list_c1,controlled_list_c2):
    class_path_clean = []
    if "<http" not in class_path:
        class_path = class_path.split("/")
    else:
        class_path = split_string_preserve_url(class_path)
    for c in class_path:
        if c == "":
            continue
        if "(from CL1)" in c:
            c = c.replace("(from CL1)", "")
            c = controlledClassReplace(c.strip(), "CL1", XPath,controlled_list_c1,controlled_list_c2)
            class_path_clean.append(wordToURL(c))
        elif "(from CL2)" in c:
            c = c.replace("(from CL2)", "")
            c = controlledClassReplace(c.strip(), "CL2", XPath,controlled_list_c1,controlled_list_c2)
            class_path_clean.append(wordToURL(c))
        else:
            class_path_clean.append(wordToURL(c.strip()))

    return class_path_clean

def parsePropertyPath(property_path):
    property_path_clean = []
    is_value = False
    if "?this" in property_path:
        property_path = property_path.replace("?this","").strip()
    else:
        raise Exception("The property path should start with ?this")
    property_path = property_path.strip()
    if property_path[-1] == ".":
        property_path = property_path[:-1].strip()
    if property_path[-1] == ">":
        is_value = True
    if "<http" not in property_path:
        property_path = property_path.split("/")
    else:
        property_path = split_string_preserve_url(property_path)
    p = property_path.pop(-1).strip()
    property_path.extend(p.split(" "))
    for p in property_path:
        if p == "":
            continue
        property_path_clean.append(wordToURL(p.strip()))
    if is_value:
        return property_path_clean[0:-1]
    return property_path_clean
def count_cm_stats(cm_file, config_file, version):
    dL = dataLoader(file_path=cm_file, config_path=config_file, cm_version=version)
    _, Class_path, Property_path, Field_XPath, cl1, cl2 , _ = dL.load()
    controlled_list_c1 = cl1["CL1"]
    controlled_list_c2 = cl2["CL2"]
    class_set, prop_set = set(), set()
    rule = 0
    multi_list = []
    for XPath, Class, Property in zip(Field_XPath, Class_path, Property_path):
        rule += 1
        # print(f"C: {Class}, P: {Property}")
        # if 'FILTER' in Property or num == 551: #TODO: to be fixed Lot and FILTER
        if 'FILTER' in Property: #TODO: to be fixed Lot and FILTER
            continue
        if ("OR" in Class) and ("{" in Property) and ("UNION" in Property):
            Class = [i for i in Class.split("OR")]
            Property = [i.replace("{","").replace("}","").strip() for i in Property.split("UNION")] 
            # Cartesian Product
            for i in range(len(Class)):
                c_list = parseClassPath(Class[i], XPath,controlled_list_c1,controlled_list_c2)
                p_list = parsePropertyPath(Property[i])
                multi_list.append((c_list, p_list))
        elif ("OR" in Class) and ("{" not in Property) and ("UNION" not in Property):
            Class = [i for i in Class.split("OR")]
            p_list = parsePropertyPath(Property)
            for c in Class:
                c_list = parseClassPath(c, XPath,controlled_list_c1,controlled_list_c2)
                multi_list.append((c_list, p_list))
        elif ("OR" not in Class) and ("{" in Property) and ("UNION" in Property):
            Property = [i.replace("{","").replace("}","").strip() for i in Property.split("UNION")]
            c_list = parseClassPath(Class, XPath,controlled_list_c1,controlled_list_c2)
            for p in Property:
                p_list = parsePropertyPath(p)
                multi_list.append((c_list, p_list))
        else:
            c_list = parseClassPath(Class, XPath,controlled_list_c1,controlled_list_c2)
            p_list = parsePropertyPath(Property)
            multi_list.append((c_list, p_list))

        for c_list, p_list in multi_list:
            if len(c_list) != len(p_list) and len(p_list)>=2 and p_list[-2] == RDF.type and str(p_list[-1]) not in ignore_list:
                extra_class.append(str(p_list[-1]))
                p_list = p_list[:-2]
                p_list.append("?value")
            class_set.update(c_list)
            prop_set.update(p_list)

        multi_list = []
        rule+=1

    remove_l = []
    for c in class_set:
        if str(c) in ignore_list:
            remove_l.append(c)
    for c in remove_l:
        class_set.remove(c)

    remove_l = []
    for p in prop_set:
        if str(p) in ignore_list:
            remove_l.append(p)
        elif str(p) in extra_class:
            remove_l.append(p)
            class_set.add(p)
    for p in remove_l:
        prop_set.remove(p)
    return rule, class_set, prop_set

def count_shacl_details(shacl_path):
    g = rdflib.Graph()
    g.parse(shacl_path, format="turtle")
    classes = {c for _, _, c in g.triples((None, SH.targetClass, None))}
    classes.update({c for _, _, c in g.triples((None, SH["class"], None))})
    props = {p for _, _, p in g.triples((None, SH.path, None))}
    restrictions = 0
    for _,p,_ in g:
        if p in [SH["class"], SH["datatype"], SH["nodeKind"]]:
            restrictions += 1
    remove_l = []
    for c in classes:
        if str(c) in ignore_list:
            remove_l.append(c)
    for c in remove_l:
        classes.remove(c)
    remove_l = []
    for p in props:
        if str(p) in ignore_list:
            remove_l.append(p)
        elif str(p) in extra_class:
            remove_l.append(p)
            classes.add(p)
    for p in remove_l:
        props.remove(p)

    return classes, props, restrictions

def evaluate_cm2shacl_on_repo(repo_root, config_file, version, rows=[]):
    repo_name = os.path.basename(repo_root)
    package_paths = sorted(glob.glob(os.path.join(repo_root, "package_*")))

    for suite in package_paths:
        package_name = os.path.basename(suite)
        cm_path = os.path.join(suite, "transformation", "conceptual_mappings.xlsx")
        output_path = suite.replace("data", "evaluation") + "/cm_shacl_close.ttl"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        cm_args = argparse.Namespace(
            cm_file=cm_path,
            config_file=config_file,
            cm_version=version,
            output_file=output_path,
            close_shapes=True,
        )

        # try:
        start = time.time()
        C2S = CMtoSHACL()
        C2S.evaluate_file(cm_args)
        duration = round(time.time() - start, 2)
        print(f"Successfully generated SHACL file in {output_path} in {duration} seconds")

        rules, cm_cls, cm_prop = count_cm_stats(cm_path, config_file, version)
        shacl_cls, shacl_prop, restriction_count = count_shacl_details(output_path)

        correct_cls = cm_cls & shacl_cls
        correct_prop = cm_prop & shacl_prop

        class_accuracy = round(len(correct_cls) / len(cm_cls), 3) if cm_cls else 0.0
        prop_accuracy = round(len(correct_prop) / len(cm_prop), 3) if cm_prop else 0.0

        print(f"CM_Class - SHACL_Class: {cm_cls - shacl_cls}")
        print(f"CM_Property - SHACL_Property: {cm_prop - shacl_prop}")
        print(f"SHACL_Class - CM_Class: {shacl_cls - cm_cls}")
        print(f"SHACL_Property - CM_Property: {shacl_prop - cm_prop}")

        rows.append([
            repo_name, package_name, rules, len(cm_cls), len(cm_prop),
            len(shacl_cls), len(shacl_prop), restriction_count, duration,
            class_accuracy, prop_accuracy
        ])

        # except Exception as e:
        #     print(f"Error processing {package_name}: {e}")
   
    # Calculate average
    avg_row = ["Average", ""] + [round(sum(r[i] for r in rows) / len(rows), 3) for i in range(2, 11)]
    rows.append(avg_row)
    return rows

def write_report(rows, output_csv):
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "source", "package", "cm_rules", "cm_classes", "cm_properties",
            "shacl_classes", "shacl_properties", "total_restrictions", "generation_time(s)",
            "class_accuracy", "property_accuracy"
        ])
        writer.writerows(rows)

    print(f"Written report to {output_csv}")


def rdf_validation(data_root="data", eval_root="evaluation"):
    # for domain in ["standardForms", "eforms"]:
    sources = ["standardForms", "eforms"]
    for domain in sources:
        domain_data_path = os.path.join(data_root, domain)
        print(f"Processing {domain}...")
        for package_path in glob.glob(os.path.join(domain_data_path, "package_*")):
            print(f"Processing package {package_path}...")
            package_name = os.path.basename(package_path)
            rdf_glob_path = "output/**/*.ttl"
            rdf_files = glob.glob(os.path.join(package_path, rdf_glob_path), recursive=True)

            if not rdf_files:
                print(f"[!] No RDF files found in {package_path}")
                continue
            # Load corresponding SHACL shape path
            eval_package_path = os.path.join(eval_root, domain, package_name).replace("data", "evaluation")
            shacl_path = os.path.join(eval_package_path, "cm_shacl_close.ttl")
            if not os.path.exists(shacl_path):
                print(f"[!] SHACL shape not found: {shacl_path}")
                continue
            print(f"Loading SHACL shape from {shacl_path}...")
            shacl_g = rdflib.Graph().parse(shacl_path)

            for rdf_path in rdf_files:
                # Determine relative path for saving report
                print(f"Processing RDF file {rdf_path}...")
                rel_path = os.path.relpath(rdf_path, start=os.path.join(data_root, domain))
                report_folder = os.path.join(eval_root, domain, os.path.dirname(rel_path)).replace("data", "evaluation")
                os.makedirs(report_folder, exist_ok=True)
                report_path = os.path.join(report_folder, "validation_report_close.ttl")

                data_g = rdflib.Graph().parse(rdf_path)
                r = validate(data_g, shacl_graph=shacl_g)
                conforms, results_graph, results_text = r
                print(f"Conforms: {conforms}")
                results_graph.serialize(destination=report_path, format="turtle")

def analyze_validation_report(report_path):
    g = Graph().parse(report_path, format="turtle")
    
    conforms = (None, SH.conforms, None) in g
    if conforms:
        result = list(g.objects(predicate=SH.conforms))[0]
        if str(result).lower() == "true":
            return True, 0
    # Count sh:ValidationResult triples
    violations = len(list(g.subjects(RDF.type, SH.ValidationResult)))
    return False, violations

def validation_report_analysis(eval_root="evaluation", output_csv="evaluation/cm2shacl_close_validation_report_analysis.csv"):
    rows = []
    summary = {"standardForms": {"total": 0, "true": 0, "violations": 0},
               "eforms": {"total": 0, "true": 0, "violations": 0}}
    sources = ["standardForms", "eforms"]
    for source in sources:
        for package_path in glob.glob(os.path.join(eval_root, source, "package_*")):
            package = os.path.basename(package_path)
            report_files = glob.glob(os.path.join(package_path, "**/validation_report_close.ttl"), recursive=True)

            for report_path in report_files:
                rdf_name = os.path.basename(os.path.dirname(report_path))
                passed, violations = analyze_validation_report(report_path)

                summary[source]["total"] += 1
                summary[source]["violations"] += violations
                if passed:
                    summary[source]["true"] += 1

                rows.append([
                    source,
                    package,
                    rdf_name,
                    str(passed),
                    violations
                ])

    # Add average rows
    for source in sources:
        total = summary[source]["total"]
        true = summary[source]["true"]
        viol = summary[source]["violations"]
        avg_row = [
            source,
            "Average",
            total,
            f"{true / total:.3f}" if total > 0 else "N/A",
            f"{viol / total:.2f}" if total > 0 else "N/A"
        ]
        rows.append(avg_row)

    # Write CSV
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "package", "rdf", "conforms", "violation_count"])
        writer.writerows(rows)

    print(f"[✓] Validation analysis written to {output_csv}")

# Evaluation part 1
# rows = []
# rows = evaluate_cm2shacl_on_repo("data/standardForms", "config.ini", "Conceptual Mapping Version 1.0", rows)
# rows = evaluate_cm2shacl_on_repo("data/eforms", "config.ini", "eForms 1.0", rows)
# write_report(rows, "evaluation/cm2shacl_eval.csv")

# Evaluation part 2
rdf_validation()
validation_report_analysis()

# rdf_g = Graph().parse("data/eforms/package_can_v1.3/output/sdk_examples_can/can_23_contracts/can_23_contracts.ttl", format="turtle")
# shacl_g = Graph().parse("evaluation/eforms/package_can_v1.3/cm_shacl.ttl", format="turtle")
# conforms, results_graph, results_text = validate(rdf_g, shacl_graph=shacl_g)
# print(f"Conforms: {conforms}")
# print(f"Results: {results_text}")
# results_graph.serialize(destination="validation_report_test.ttl", format="turtle")
