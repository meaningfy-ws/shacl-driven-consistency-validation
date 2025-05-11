import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import glob
import rdflib
from rdflib.namespace import RDF, OWL, Namespace
from rdflib import URIRef
from collections import defaultdict
import argparse
from cm2shacl.data_load import dataLoader
import openpyxl
import json
import re
from cm2shacl.utils import json_load, combine_shapes_with_same_path

RR = rdflib.Namespace("http://www.w3.org/ns/r2rml#")
vocab = json_load("src/vocabulary/default_vocabulary_prefixes.json")
vocab_exceptions = ["at-voc"]

owl_total_classes, owl_total_properties = set(), set()
rml_total_classes, rml_total_properties = set(), set()
cm_total_classes, cm_total_properties = set(), set()


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
    cm_total_classes.update(class_set)
    cm_total_properties.update(prop_set)
    return rule, len(class_set), len(prop_set)

def count_rml_stats(rml_graph):
    triple_maps = {s for s in rml_graph.subjects(RDF.type, RR.TriplesMap)}
    pom_subjects = {s for s, _, _ in rml_graph.triples((None, RR.predicateObjectMap, None))}
    predicates = {str(o) for _, _, o in rml_graph.triples((None, RR.predicate, None))}
    classes = {str(o) for _, _, o in rml_graph.triples((None, RR['class'], None))}


    remove_l = []
    for c in classes:
        if str(c) in ignore_list:
            remove_l.append(c)
    for c in remove_l:
        classes.remove(c)
    remove_l = []
    for p in predicates:
        if str(p) in ignore_list:
            remove_l.append(p)
    for p in remove_l:
        predicates.remove(p)
    
    rml_total_classes.update(classes)
    rml_total_properties.update(predicates)


    return len(triple_maps), len(pom_subjects), len(predicates), len(classes)

def count_owl_stats(owl_graph):
    owl_classes = {s for s, _, _ in owl_graph.triples((None, RDF.type, OWL.Class))}
    obj_props = {s for s, _, _ in owl_graph.triples((None, RDF.type, OWL.ObjectProperty))}
    data_props = {s for s, _, _ in owl_graph.triples((None, RDF.type, OWL.DatatypeProperty))}

    remove_l = []
    for c in owl_classes:
        if c.startswith("n"):
            remove_l.append(c)
    for c in remove_l:
        owl_classes.remove(c)

    remove_l = []
    for p in obj_props:
        if str(p) in ignore_list:
            remove_l.append(p)
    for p in remove_l:
        obj_props.remove(p)
    remove_l = []
    for p in data_props:
        if str(p) in ignore_list:
            remove_l.append(p)
    for p in remove_l:
        data_props.remove(p)
    remove_l = []
    for c in owl_classes:
        if str(c) in ignore_list:
            remove_l.append(c)
    for c in remove_l:
        owl_classes.remove(c)

    owl_total_classes.update(owl_classes)
    owl_total_properties.update(obj_props)
    owl_total_properties.update(data_props)

    obj_props.update(data_props)

    return len(owl_classes), len(obj_props)

def process_repo(repo_path, config_file, version):
    suite_stats = []
    ontology_path = os.path.join(repo_path, "ontology","ontology.ttl")
    owl_graph = rdflib.Graph().parse(ontology_path, format="turtle")
    # for owl_file in glob.glob(os.path.join(ontology_path, "*.ttl")) + glob.glob(os.path.join(ontology_path, "*.owl")):
    #     owl_graph.parse(owl_file)

    print(f"Parsing OWL files in {ontology_path}...")
    owl_classes, owl_properties = count_owl_stats(owl_graph)
    print(f"Parsed {owl_classes} OWL classes and {owl_properties} OWL properties.")

    print(f"Parsing RML and CM files in {repo_path}...")
    for suite_path in sorted(glob.glob(os.path.join(repo_path, "package_*"))):
        suite_name = os.path.basename(suite_path)
        rml_graph = rdflib.Graph()
        rml_path = os.path.join(suite_path, "transformation/mappings")
        for rml_file in glob.glob(os.path.join(rml_path, "*.ttl")):
            rml_graph.parse(rml_file, format="turtle")

        tm, pom, rml_prop, rml_class = count_rml_stats(rml_graph)

        cm_file = os.path.join(suite_path, "transformation", "conceptual_mappings.xlsx")
        if os.path.exists(cm_file):
            try:
                rules, cm_class, cm_prop = count_cm_stats(cm_file, config_file, version)
            except Exception as e:
                print(f"Error parsing {cm_file}: {e}")
                rules, cm_class, cm_prop = 0, 0, 0
        else:
            rules, cm_class, cm_prop = 0, 0, 0

        suite_stats.append({
            "suite": suite_name,
            "rules": rules,
            "cm_class": cm_class,
            "cm_property": cm_prop,
            "triple_maps": tm,
            "predicate_object_maps": pom,
            "rml_class": rml_class,
            "rml_property": rml_prop
        })

    return suite_stats, owl_classes, owl_properties


def compute_overlap_stats(cm_set, rml_set, owl_set):
    # all_set = cm_set | rml_set | owl_set
    # return {
    #     "total": len(all_set),
    #     "only_cm": len(cm_set - rml_set - owl_set),
    #     "only_rml": len(rml_set - cm_set - owl_set),
    #     "only_owl": len(owl_set - cm_set - rml_set),
    #     "cm_rml": len(cm_set & rml_set - owl_set),
    #     "cm_owl": len(cm_set & owl_set - rml_set),
    #     "rml_owl": len(rml_set & owl_set - cm_set),
    #     "all_three": len(cm_set & rml_set & owl_set)
    # }
    cm_set, rml_set, owl_set = set(cm_set), set(rml_set), set(owl_set)
    venn_data = {
        "100": len(cm_set - rml_set - owl_set),
        "010": len(rml_set - cm_set - owl_set),
        "001": len(owl_set - cm_set - rml_set),
        "110": len(cm_set & rml_set - owl_set),
        "101": len(cm_set & owl_set - rml_set),
        "011": len(rml_set & owl_set - cm_set),
        "111": len(cm_set & rml_set & owl_set)
    }
    return venn_data

def generate_stats(repo, config_path, version):

    return {
        "class_stats": compute_overlap_stats(cm_total_classes, rml_total_classes, owl_total_classes),
        "property_stats": compute_overlap_stats(cm_total_properties, rml_total_properties, owl_total_properties),
    }

def write_report(std_stats, std_owl_c, std_owl_p, eform_stats, eform_owl_c, eform_owl_p, output_file):
    def summarize(stats):
        count = len(stats)
        avg = lambda key: sum(s[key] for s in stats) / count if count else 0
        return {
            "count": count,
            "avg_rules": avg("rules"),
            "avg_tm": avg("triple_maps"),
            "avg_pom": avg("predicate_object_maps"),
            "avg_cm_class": avg("cm_class"),
            "avg_cm_prop": avg("cm_property"),
            "avg_rml_class": avg("rml_class"),
            "avg_rml_prop": avg("rml_property")
        }

    with open(output_file, "w") as f:
        f.write("==== Per Suite Statistics ====\n\n")
        f.write("Standard Forms:\n")
        for s in std_stats:
            f.write(f"{s['suite']}: Rules={s['rules']}, CM Class={s['cm_class']}, CM Prop={s['cm_property']}, "
                    f"TM={s['triple_maps']}, POM={s['predicate_object_maps']}, "
                    f"RML Class={s['rml_class']}, RML Prop={s['rml_property']}\n")
        f.write("\nEForms:\n")
        for s in eform_stats:
            f.write(f"{s['suite']}: Rules={s['rules']}, CM Class={s['cm_class']}, CM Prop={s['cm_property']}, "
                    f"TM={s['triple_maps']}, POM={s['predicate_object_maps']}, "
                    f"RML Class={s['rml_class']}, RML Prop={s['rml_property']}\n")

        f.write("\n==== Summary ====\n\n")
        s_summary = summarize(std_stats)
        f.write(f"Standard Forms: Suites={s_summary['count']}, Avg Rules={s_summary['avg_rules']:.1f}, "
                f"Avg TM={s_summary['avg_tm']:.1f}, Avg POM={s_summary['avg_pom']:.1f}, "
                f"Avg CM Class={s_summary['avg_cm_class']:.1f}, Avg CM Prop={s_summary['avg_cm_prop']:.1f}, "
                f"Avg RML Class={s_summary['avg_rml_class']:.1f}, Avg RML Prop={s_summary['avg_rml_prop']:.1f}, "
                f"OWL Class={std_owl_c}, OWL Prop={std_owl_p}\n")

        e_summary = summarize(eform_stats)
        f.write(f"EForms: Suites={e_summary['count']}, Avg Rules={e_summary['avg_rules']:.1f}, "
                f"Avg TM={e_summary['avg_tm']:.1f}, Avg POM={e_summary['avg_pom']:.1f}, "
                f"Avg CM Class={e_summary['avg_cm_class']:.1f}, Avg CM Prop={e_summary['avg_cm_prop']:.1f}, "
                f"Avg RML Class={e_summary['avg_rml_class']:.1f}, Avg RML Prop={e_summary['avg_rml_prop']:.1f}, "
                f"OWL Class={eform_owl_c}, OWL Prop={eform_owl_p}\n")

if __name__ == "__main__":
    standardForms_path = "data/standardForms"
    eForms_path = "data/eforms"
    output_path = "evaluation/report.txt"

    std_stats, std_c, std_p = process_repo(standardForms_path, "config.ini", "Conceptual Mapping Version 1.0")

    def save_entity_set_to_txt(entity_set, filepath):

        with open(filepath, 'w') as f:
            for item in sorted(entity_set):
                f.write(f"{item}\n")


    # 保存到6个文件
    os.makedirs("evaluation/venn_input/standardForms", exist_ok=True)
    save_entity_set_to_txt(cm_total_classes, "evaluation/venn_input/standardForms/cm_classes.txt")
    save_entity_set_to_txt(rml_total_classes, "evaluation/venn_input/standardForms/rml_classes.txt")
    save_entity_set_to_txt(owl_total_classes, "evaluation/venn_input/standardForms/owl_classes.txt")

    save_entity_set_to_txt(cm_total_properties, "evaluation/venn_input/standardForms/cm_properties.txt")
    save_entity_set_to_txt(rml_total_properties, "evaluation/venn_input/standardForms/rml_properties.txt")
    save_entity_set_to_txt(owl_total_properties, "evaluation/venn_input/standardForms/owl_properties.txt")

    owl_total_classes, owl_total_properties = set(), set()
    rml_total_classes, rml_total_properties = set(), set()
    cm_total_classes, cm_total_properties = set(), set()
    eform_stats, eform_c, eform_p = process_repo(eForms_path, "config.ini", "eForms 1.0")
    
    os.makedirs("evaluation/venn_input/eForms", exist_ok=True)
    save_entity_set_to_txt(cm_total_classes, "evaluation/venn_input/eForms/cm_classes.txt")
    save_entity_set_to_txt(rml_total_classes, "evaluation/venn_input/eForms/rml_classes.txt")
    save_entity_set_to_txt(owl_total_classes, "evaluation/venn_input/eForms/owl_classes.txt")
    save_entity_set_to_txt(cm_total_properties, "evaluation/venn_input/eForms/cm_properties.txt")
    save_entity_set_to_txt(rml_total_properties, "evaluation/venn_input/eForms/rml_properties.txt")
    save_entity_set_to_txt(owl_total_properties, "evaluation/venn_input/eForms/owl_properties.txt")
    # save_entity_set_to_txt(cm_total_classes, "venn_input/cm_classes.txt")

    write_report(std_stats, std_c, std_p, eform_stats, eform_c, eform_p, output_path)
    print(f"Report generated successfully in {output_path}")

    stats = {
        "standardForms": generate_stats("data/standardForms", "config.ini", "Conceptual Mapping Version 1.0"),
        "eForms": generate_stats("data/eforms", "config.ini", "eForms 1.0")
    }
    with open("evaluation/venn_input/venn_overlap_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print("Venn diagram data saved to venn_overlap_stats.json")