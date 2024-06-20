import rdflib
from rdflib import Graph, URIRef, Literal, Namespace, BNode
from rdflib.namespace import RDF, RDFS,XSD, SH
from pyshacl import validate
import argparse
import re

from data_load import dataLoader
from utils import json_load

class CMtoSHACL():
    def __init__(self):
        self.vocab = json_load("src/vocabulary/default_vocabulary_prefixes.json")
        self.vocab_exceptions = ["at-voc"]
        self.datatype = json_load("src/vocabulary/xmlschema11_2.json")

        self.g = Graph()
        self.g.bind("sh", SH)
        self.g.bind("xsd", XSD)
        self.g.bind("rdfs", RDFS)
        self.g.bind("rdf", RDF)
        self.g.bind("epo", Namespace(self.vocab["epo"]))

        self.indentifiers = {}

    def translate(self):
        # load the data
        self.Field_XPath, self.Class_path, self.Property_path = self.dL.load_rules()

        # loop through the rules
        for XPath, Class, Property in zip(self.Field_XPath, self.Class_path, self.Property_path):
            
            if "{" in Property and "UNION" in Property:
                Property = [i.replace("{","").replace("}","").strip() for i in Property.split("UNION")]
                for p in Property:
                    c_list = self.parseClassPath(Class)
                    p_list = self.parsePropertyPath(p)
            else:
                c_list = self.parseClassPath(Class)
                p_list = self.parsePropertyPath(Property)
            
            if len(c_list) != len(p_list):
                print("parsing the rule: ", Class, Property)
                print("c_list: ", c_list)
                print("p_list: ", p_list)
            else:
                for index in range(len(c_list) - 1):
                    c = c_list[index]
                    p = p_list[index]
                    if index == len(c_list)-2:
                        self.addNodePropertyShape(c, p, c_list[index+1], p_list[index+1], True)
                    else:
                        self.addNodePropertyShape(c, p, c_list[index+1], p_list[index+1])
                

    def addNodePropertyShape(self, c, p, next_c, next_p, is_last=False):
        c = URIRef(c)
        p = URIRef(p)
        if c not in self.indentifiers:
            self.indentifiers[c] = {}
            self.g.add((c, RDF.type, SH.NodeShape))
            self.g.add((c, SH.targetClass, c))
        if p not in self.indentifiers[c]:
            self.indentifiers[c][p] = BNode()
            self.g.add((c, SH.property, self.indentifiers[c][p]))
            self.g.add((self.indentifiers[c][p], SH.path, p))
            
        if is_last == False and next_c != None:
            self.g.add((self.indentifiers[c][p], SH["class"], URIRef(next_c)))
            self.g.add((self.indentifiers[c][p], SH["nodeKind"], SH["IRI"]))
        elif is_last == True:
            next_c_type = self.checkType(next_c)
            if next_c_type == "class":
                self.g.add((self.indentifiers[c][p], SH["class"], URIRef(next_c)))
                self.g.add((self.indentifiers[c][p], SH["nodeKind"], SH["IRI"]))
            elif next_c_type == "datatype":
                self.g.add((self.indentifiers[c][p], SH["datatype"], next_c))
                self.g.add((self.indentifiers[c][p], SH["nodeKind"], SH["Literal"]))
            elif next_c_type == None:
                self.g.add((self.indentifiers[c][p], SH["nodeKind"], SH["IRI"]))
            if next_p != "?value":
                self.g.add((self.indentifiers[c][p], SH["hasValue"], Literal(next_p)))
                #TODO to be added nodeKind


            
    def parseClassPath(self, class_path):
        class_path_clean = []
        if "<http" not in class_path:
            class_path = class_path.split("/")
        else:
            class_path = self.split_string_preserve_url(class_path)
        for c in class_path:
            if c == "":
                continue
            if "(from CL1)" in c:
                c = c.replace("(from CL1)", "")
                c = self.controlledClassReplace(c.strip(), "CL1")
                class_path_clean.append(self.wordToURL(c))
            elif "(from CL2)" in c:
                c = c.replace("(from CL2)", "")
                c = self.controlledClassReplace(c.strip(), "CL2")
                class_path_clean.append(self.wordToURL(c))
            else:
                class_path_clean.append(self.wordToURL(c.strip()))
        
        # # Check final element is class or datatype
        # if class_path_clean[-1][1] == None:
        #     class_path_clean[-1] = (None, None)
        # else:
        #     t = self.checkType(class_path_clean[-1][1])
        #     class_path_clean[-1] = (SH[t], class_path_clean[-1][1])
        return class_path_clean

            
    def parsePropertyPath(self, property_path):
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
            property_path = self.split_string_preserve_url(property_path)
        p = property_path.pop(-1).strip()
        property_path.extend(p.split(" "))
        for p in property_path:
            if p == "":
                continue
            property_path_clean.append(self.wordToURL(p.strip()))

        # # Check final element is variable or constant IRI
        # if property_path_clean[-1][1] == "?value":
        #     pass
        # else:
        #     property_path_clean[-1] = (SH["hasValue"], property_path_clean[-1][1]) # TODO: To be fixed

        return property_path_clean

    def controlledClassReplace(self, c, list_type):
        return c # TODO: implement this

    def wordToURL(self, word):
        if word == "?value" or word == "true" or word == "false":
            return word
        
        # elif word.startswith("<") and (re.match(r'https?://', word[1:-1]) or re.match(r'http?://', word[1:-1])): #TODO: ASK FOR THIS TYPO
        elif word.startswith("<"):
            return URIRef(word[1:-1])

        elif word == "a":
            return RDF.type

        elif ":" in word:
            word = word.split(":")
            if word[0] in self.vocab:
                return URIRef(self.vocab[word[0]] + word[1])
            elif word[0] in self.vocab_exceptions:
                return None
            else:
                raise Exception(f"Prefix {word[0]} not found in the vocabulary")
        else:
            raise Exception(f"Term {word} is not a URL or a prefix")

    def checkType(self, url):
        if url == None:
            return None
        elif str(url).startswith("http://www.w3.org/2001/XMLSchema#"):
            return "datatype"
        elif str(url).startswith("http://www.w3.org/1999/02/22-rdf-syntax-ns#"):
            return "datatype"
        else:
            return "class"

    def split_string_preserve_url(self, input_string):
        urls = re.findall(r'<[^>]+>', input_string)

        for i, url in enumerate(urls):
            input_string = input_string.replace(url, f'URL_PLACEHOLDER_{i}')

        parts = input_string.split('/')
        

        for i, part in enumerate(parts):
            if f'URL_PLACEHOLDER_' in part:
                parts[i] = parts[i].replace(f"URL_PLACEHOLDER_{part.split('_')[-1]}", urls[int(part.split('_')[-1])])
            
        return parts


    def writeShapeToFile(self, file_name):
        self.g.serialize(destination=file_name, format='turtle')
        # write comments to the beginning of the file
        metaData_info, baseXpath = self.dL.load_metadata()
        with open(file_name, 'r') as original: data = original.read()
        with open(file_name, 'w') as modified: modified.write(f"{metaData_info}\n" + data)


    def evaluate_file(self, args):
        # load the data
        self.dL = dataLoader(args.cm_file)

        # start the translation
        self.translate()

        # validate the SHACL
        shaclValidation = Graph()
        shaclValidation.parse("https://www.w3.org/ns/shacl-shacl")

        r = validate(self.g, shacl_graph=shaclValidation)
        if not r[0]:
            print(r[2])

        if args.output_file:
            self.writeShapeToFile(args.output_file)
        else:
            self.writeShapeToFile(args.cm_file + ".shape.ttl")
        
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Translate Conceptual Mapping to SHACL')
    parser.add_argument("cm_file",  help='conceptual mapping file location', type=str)
    parser.add_argument("-o", "--output_file", help='output file location', type=str, default=None)
    args = parser.parse_args()

    C2S = CMtoSHACL()
    C2S.evaluate_file(args)