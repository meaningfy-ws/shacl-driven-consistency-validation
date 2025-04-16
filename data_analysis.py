import os
import glob
import rdflib
from rdflib.namespace import RDF, OWL, Namespace
from rdflib import URIRef
from collections import defaultdict
import argparse
from src.cm2shacl.data_load import dataLoader
import openpyxl
import re
from src.cm2shacl.utils import json_load, combine_shapes_with_same_path

RR = Namespace("http://www.w3.org/ns/r2rml#")
vocab = json_load("src/vocabulary/default_vocabulary_prefixes.json")
vocab_exceptions = ["at-voc"]

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

def controlledClassReplace(c, list_type, XPath,controlled_list_c1):
    class_XPath_fragment = XPath.split("/")[1]
    if list_type == "CL1":
        c = controlled_list_c1.get(class_XPath_fragment, c)
    elif list_type == "CL2":
        c = c #TODO: DOUBLE CHECK CL2 CONTROLLED LIST
    return c 

def parseClassPath(class_path, XPath,controlled_list_c1):
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
            c = controlledClassReplace(c.strip(), "CL1", XPath,controlled_list_c1)
            class_path_clean.append(wordToURL(c))
        elif "(from CL2)" in c:
            c = c.replace("(from CL2)", "")
            c = controlledClassReplace(c.strip(), "CL2", XPath,controlled_list_c1)
            class_path_clean.append(wordToURL(c))
        else:
            class_path_clean.append(wordToURL(c.strip()))

    return class_path_clean

def parsePropertyPath(property_path):
    property_path_clean = []
    if "?this" in property_path:
        property_path = property_path.replace("?this","").strip()
    else:
        raise Exception("The property path should start with ?this")
    property_path = property_path.strip()
    if property_path[-1] == ".":
        property_path = property_path[:-1]
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

    # # Check final element is variable or constant IRI
    # if property_path_clean[-1][1] == "?value":
    #     pass
    # else:
    #     property_path_clean[-1] = (SH["hasValue"], property_path_clean[-1][1]) # TODO: To be fixed

    return property_path_clean

def count_rml_stats(rml_graph):
    triple_maps = {s for s in rml_graph.subjects(RDF.type, RR.TriplesMap)}
    pom_subjects = {s for s, _, _ in rml_graph.triples((None, RR.predicateObjectMap, None))}
    predicates = {str(o) for _, _, o in rml_graph.triples((None, RR.predicate, None))}
    classes = {str(o) for _, _, o in rml_graph.triples((None, RR['class'], None))}
    return len(triple_maps), len(pom_subjects), len(predicates), len(classes)

def count_owl_stats(owl_graph):
    class_count = len({s for s, _, _ in owl_graph.triples((None, RDF.type, OWL.Class))})
    obj_props = {s for s, _, _ in owl_graph.triples((None, RDF.type, OWL.ObjectProperty))}
    data_props = {s for s, _, _ in owl_graph.triples((None, RDF.type, OWL.DatatypeProperty))}
    return class_count, len(obj_props.union(data_props))

def count_cm_stats(cm_file, config_file, version):
    
    dL = dataLoader(file_path=cm_file, config_path=config_file, cm_version=version)
    _, Class_path, Property_path, Field_XPath, cl1, _ = dL.load()
    controlled_list_c1 = cl1["CL1"]
    class_set, prop_set = set(), set()
    rule,num = 0,0
    for XPath, Class, Property in zip(Field_XPath, Class_path, Property_path):
        rule += 1
        # print(f"C: {Class}, P: {Property}")
        if 'FILTER' in Property or num == 551: #TODO: to be fixed Lot and FILTER
            continue
        if "{" in Property and "UNION" in Property:
            Property = [i.replace("{","").replace("}","").strip() for i in Property.split("UNION")]
            for p in Property:
                c_list = parseClassPath(Class, XPath,controlled_list_c1)
                p_list = parsePropertyPath(p)
        else:
            c_list = parseClassPath(Class, XPath,controlled_list_c1)
            p_list = parsePropertyPath(Property)
        
        if len(c_list) != len(p_list):
            if len(p_list) == 2 and p_list[0] == RDF.type:
                pass
            else:
                print("The length of the rule is not consistent: ", Class, Property)
                print("class list: ", c_list)
                print("property list: ", p_list)
        else:
            rule+=1

        class_set.update(c_list)
        prop_set.update(p_list)

        # if cls and prop:
        #     cls_list = cls.split("/") if "<http" not in cls else [x for x in cls.split("/") if x.startswith("<http")]
        #     class_set.update(cls_list)
        #     prop = prop.replace("?this", "").strip(".")
        #     prop_list = prop.split("/") if "<http" not in prop else [x for x in prop.split("/") if x.startswith("<http")]
        #     prop_set.update(prop_list)
    return rule, len(class_set), len(prop_set)



def process_repo(repo_path, config_file, version):
    suite_stats = []
    ontology_path = os.path.join(repo_path, "ontology")
    owl_graph = rdflib.Graph()
    for owl_file in glob.glob(os.path.join(ontology_path, "*.ttl")) + glob.glob(os.path.join(ontology_path, "*.owl")):
        owl_graph.parse(owl_file)

    print(f"Parsing OWL files in {ontology_path}...")
    owl_classes, owl_properties = count_owl_stats(owl_graph)

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
    output_path = "data/report.txt"

    std_stats, std_c, std_p = process_repo(standardForms_path, "config.ini", "Conceptual Mapping Version 1.0")
    eform_stats, eform_c, eform_p = process_repo(eForms_path, "config.ini", "eForms 1.0")

    write_report(std_stats, std_c, std_p, eform_stats, eform_c, eform_p, output_path)
    print(f"Report generated successfully in {output_path}")