import rdflib
from rdflib import Graph, URIRef, Literal, Namespace, BNode
from rdflib.namespace import RDF, RDFS,XSD, SH
from pyshacl import validate
import re

from .data_load import dataLoader
from .utils import json_load, combine_shapes_with_same_path

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
        self.g.bind("dcterms", Namespace(self.vocab["dct"]))

        self.dctsource = Namespace(self.vocab["dct"]).source
        
        self.identifiers = {}
        self.shaclinDict = {}
        self.constraintDict = {SH["datatype"]:{}, SH["class"]:{}}
        
    def translate(self):
        # load the data
        self.metaData_info, self.Class_path, self.Property_path, self.Field_XPath, self.controlled_list_c1, self.field_id = self.dL.load()
        self.controlled_list_c1 = self.controlled_list_c1["CL1"]

        # loop through the rules
        num = 0
        for XPath, Class, Property, ID in zip(self.Field_XPath, self.Class_path, self.Property_path, self.field_id):
            num += 1
            print(f"Processing Rule {num}...")
            # print(f"C: {Class}, P: {Property}")
            if 'FILTER' in Property or num == 551: #TODO: to be fixed Lot and FILTER
                continue
            if "{" in Property and "UNION" in Property:
                Property = [i.replace("{","").replace("}","").strip() for i in Property.split("UNION")]
                for p in Property:
                    c_list = self.parseClassPath(Class, XPath)
                    p_list = self.parsePropertyPath(p)
            else:
                c_list = self.parseClassPath(Class, XPath)
                p_list = self.parsePropertyPath(Property)
            
            if len(c_list) != len(p_list):
                if len(p_list) == 2 and p_list[0] == RDF.type:
                    pass
                else:
                    print("The length of the rule is not consistent: ", Class, Property)
                    print("class list: ", c_list)
                    print("property list: ", p_list)
            else:
                for index in range(len(c_list) - 1):
                    c = c_list[index]
                    p = p_list[index]
                    if index == len(c_list)-2:
                        self.addNodePropertyShape(c, p, c_list[index+1], p_list[index+1], ID, True)
                    else:
                        self.addNodePropertyShape(c, p, c_list[index+1], p_list[index+1], ID)

        #self.addSHACLin()
        # self.addSHACLconstraints()
        # self.addDisjunctionShapes()
        self.g = combine_shapes_with_same_path(self.g)
                

    def _addNodePropertyShape(self, c, p, next_c, next_p, ID, is_last=False):
        c = URIRef(c)
        p = URIRef(p)
        if c not in self.identifiers:
            self.identifiers[c] = {}
            self.g.add((c, RDF.type, SH.NodeShape))
            self.g.add((c, self.dctsource, Literal(ID)))
            if self.close:
                self.g.add((c, SH.closed, Literal("true", datatype=XSD.boolean)))
            self.g.add((c, SH.targetClass, c))
            self.g.add((c, SH["class"],c))
            self.g.add((c, SH["nodeKind"], SH["IRI"]))
        if p not in self.identifiers[c]:
            self.identifiers[c][p] = BNode()
            self.g.add((c, SH.property, self.identifiers[c][p]))
            self.g.add((self.identifiers[c][p], SH.path, p))
            self.g.add((self.identifiers[c][p], self.dctsource, Literal(ID)))
            
        if is_last == False and next_c != None:
            self.g.add((self.identifiers[c][p], SH["class"], URIRef(next_c)))
            self.g.add((self.identifiers[c][p], SH["nodeKind"], SH["IRI"]))
        elif is_last == True:
            next_c_type = self.checkType(next_c)
            if next_c_type == "class":
                # self.g.add((self.identifiers[c][p], SH["class"], URIRef(next_c)))
                currentClass = self.constraintDict[SH["class"]].get(self.identifiers[c][p], [])
                currentClass.append(URIRef(next_c))
                self.constraintDict[SH["class"]][self.identifiers[c][p]] = currentClass
                self.g.add((self.identifiers[c][p], SH["nodeKind"], SH["IRI"]))
            elif next_c_type == "datatype":
                # self.g.add((self.identifiers[c][p], SH["datatype"], next_c))
                currentDatatype = self.constraintDict[SH["datatype"]].get(self.identifiers[c][p], [])
                currentDatatype.append(next_c)
                self.constraintDict[SH["datatype"]][self.identifiers[c][p]] = currentDatatype
                self.g.add((self.identifiers[c][p], SH["nodeKind"], SH["Literal"]))
            elif next_c_type == None:
                self.g.add((self.identifiers[c][p], SH["nodeKind"], SH["IRI"]))
            if next_p != "?value":
                # self.g.add((self.identifiers[c][p], SH["hasValue"], Literal(next_p)))
                currentIn = self.shaclinDict.get(self.identifiers[c][p], [])
                currentIn.append(Literal(next_p))
                self.shaclinDict[self.identifiers[c][p]] = currentIn
                #TODO to be added nodeKind

    def addNodePropertyShape(self, c, p, next_c, next_p, ID, is_last=False):
        c = URIRef(c)
        p = URIRef(p)
        if c not in self.identifiers:
            self.identifiers[c] = {}
            self.g.add((c, RDF.type, SH.NodeShape))
            self.g.add((c, self.dctsource, Literal(ID)))
            if self.close:
                self.g.add((c, SH.closed, Literal("true", datatype=XSD.boolean)))
            self.g.add((c, SH.targetClass, c))
            self.g.add((c, SH["class"],c))
            self.g.add((c, SH["nodeKind"], SH["IRI"]))
            self.g
        if p not in self.identifiers[c]:
            ps = BNode()
            self.identifiers[c][p] = [ps]
            self.g.add((c, SH.property, ps))
            self.g.add((ps, SH.path, p))
            self.g.add((ps, self.dctsource, Literal(ID)))
        else:
            ps = BNode()
            self.identifiers[c][p].append(ps)
            self.g.add((c, SH.property, ps))
            self.g.add((ps, SH.path, p))
            self.g.add((ps, self.dctsource, Literal(ID)))
            
        if is_last == False and next_c != None:
            self.g.add((ps, SH["class"], URIRef(next_c)))
            self.g.add((ps, SH["nodeKind"], SH["IRI"]))
        elif is_last == True:
            next_c_type = self.checkType(next_c)
            if next_c_type == "class":
                # self.g.add((self.identifiers[c][p], SH["class"], URIRef(next_c)))
                # currentClass = self.constraintDict[SH["class"]].get(self.identifiers[c][p], [])
                # currentClass.append(URIRef(next_c))
                # self.constraintDict[SH["class"]][self.identifiers[c][p]] = currentClass
                self.g.add((ps, SH["nodeKind"], SH["IRI"]))
                self.g.add((ps, SH["class"], URIRef(next_c)))
            elif next_c_type == "datatype":
                # self.g.add((self.identifiers[c][p], SH["datatype"], next_c))
                # currentDatatype = self.constraintDict[SH["datatype"]].get(self.identifiers[c][p], [])
                # currentDatatype.append(next_c)
                # self.constraintDict[SH["datatype"]][self.identifiers[c][p]] = currentDatatype
                self.g.add((ps, SH["nodeKind"], SH["Literal"]))
                self.g.add((ps, SH["datatype"], next_c))
            elif next_c_type == None:
                self.g.add((ps, SH["nodeKind"], SH["IRI"]))
            if next_p != "?value":
                # self.g.add((self.identifiers[c][p], SH["hasValue"], Literal(next_p)))
                # currentIn = self.shaclinDict.get(self.identifiers[c][p], [])
                # currentIn.append(Literal(next_p))
                # self.shaclinDict[self.identifiers[c][p]] = currentIn
                bn = BNode()
                self.g.add((ps, SH["in"], bn))
                if next_p.startswith("http"):
                    self.g.add((bn, RDF.first, URIRef(next_p)))
                else:
                    self.g.add((bn, RDF.first, Literal(next_p)))
                self.g.add((bn, RDF.rest, RDF.nil))
                #TODO to be added nodeKind


    def addSHACLin(self):
        for k, v in self.shaclinDict.items():
            v = list(set(v))
            bn = BNode()
            # translate element in v to a list of literals
            self.g.add((k,SH["in"],bn))
            for i in v[:-1]:
                if i == "true" or i == "false":
                    i = Literal(i, datatype=XSD.boolean)
                else:
                    i = Literal(i)
                self.g.add((bn,RDF.first,i))
                nextBn = BNode()
                self.g.add((bn,RDF.rest,nextBn))
                bn = nextBn
            self.g.add((bn,RDF.first,v[-1]))
            self.g.add((bn,RDF.rest,RDF.nil))

    
    def addDisjunctionShapes(self):
        for ns_class, ps_properties in self.identifiers.items():
            for p, ps_list in ps_properties.items():
                if len(ps_list) == 1:
                    continue
                bn = BNode()
                self.g.add((ns_class,SH["or"],bn))
                for i in ps_list[:-1]:
                    self.g.remove((ns_class, SH.property, i))
                    bn_prop = BNode()
                    self.g.add((bn, RDF.first, bn_prop))
                    self.g.add((bn_prop, SH.property, i))
                    nextBn = BNode()
                    self.g.add((bn,RDF.rest,nextBn))
                    bn = nextBn
                self.g.remove((ns_class, SH.property, ps_list[-1]))
                bn_prop = BNode()
                self.g.add((bn, RDF.first, bn_prop))
                self.g.add((bn_prop, SH.property, ps_list[-1]))
                self.g.add((bn,RDF.rest,RDF.nil))

    def _addSHACLconstraints(self):
        # to keep consistent and avoid unsatisfiable shapes
        for constraint, valueDict in self.constraintDict.items():
            for k, v in valueDict.items():
                # remove duplicates
                v = list(set(v))
                if len(v) == 1:
                    self.g.add((k,constraint,v[0]))
                else:
                    bn = BNode()
                    self.g.add((k,SH["or"],bn))
                    for i in v[:-1]:
                        datatypeBn = BNode()
                        self.g.add((bn,RDF.first,datatypeBn))
                        self.g.add((datatypeBn,constraint,i))
                        nextBn = BNode()
                        self.g.add((bn,RDF.rest,nextBn))
                        bn = nextBn
                    datatypeBn = BNode()
                    self.g.add((bn,RDF.first,datatypeBn))
                    self.g.add((datatypeBn,constraint,v[-1]))
                    self.g.add((bn,RDF.rest,RDF.nil))

    def parseClassPath(self, class_path, XPath):
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
                c = self.controlledClassReplace(c.strip(), "CL1", XPath)
                class_path_clean.append(self.wordToURL(c))
            elif "(from CL2)" in c:
                c = c.replace("(from CL2)", "")
                c = self.controlledClassReplace(c.strip(), "CL2", XPath)
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

    def controlledClassReplace(self, c, list_type, XPath):
        class_XPath_fragment = XPath.split("/")[1]
        if list_type == "CL1":
            c = self.controlled_list_c1.get(class_XPath_fragment, c)
        elif list_type == "CL2":
            c = c #TODO: DOUBLE CHECK CL2 CONTROLLED LIST
        return c 

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
        with open(file_name, 'r') as original: data = original.read()
        with open(file_name, 'w') as modified: modified.write(f"{self.metaData_info}\n" + data)


    def evaluate_file(self, args):
        # Load whether to close shapes
        self.close = args.close_shapes

        # load the data
        self.dL = dataLoader(file_path=args.cm_file, config_path=args.config_file, cm_version=args.cm_version)

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
        
