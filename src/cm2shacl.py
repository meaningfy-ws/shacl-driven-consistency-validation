import rdflib
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS,XSD, SH
from data_load import dataLoader

class CM2toSHACL():
    def __init__(self):
        self.vocab = json_load("src/vocabulary/default_vocabulary_prefixes.json")
        self.datatype = json_load("src/vocabulary/xmlschema11_2.json")

        self.g = Graph()
        self.g.bind("sh", SH)
        self.g.bind("xsd", XSD)
        self.g.bind("rdfs", RDFS)
        self.g.bind("rdf", RDF)

    def translate(self):
        # load the data
        self.Field_XPath, self.Class_path, self.Property_path = self.dL.load_rules()

        # loop through the rules
        for XPath, Class, Property in zip(self.Field_XPath, self.Class_path, self.Property_path):
            pass

    def parseClassPath(self, class_path):
        class_path_clean = []
        for c in class_path.split("/"):
            if "(from CL1)" in c:
                c = c.replace("(from CL1)", "")
                c = self.controlledClassReplace(c.strip(), "CL1")
                class_path_clean.append((SH["class"], self.wordToURL(c)))
            elif "(from CL2)" in c:
                c = c.replace("(from CL2)", "")
                c = self.controlledClassReplace(c.strip(), "CL2")
                class_path_clean.append((SH["class"], self.wordToURL(c)))
            else:
                class_path_clean.append((SH["class"], self.wordToURL(c.strip())))
        
        # Check final element is class or datatype
        t = self.checkType(class_path_clean[-1][1])
        if t == "datatype":
            class_path_clean[-1] = (SH["datatype"], class_path_clean[-1][1])
        else:
            pass
        return class_path_clean

            
    def parsePropertyPath(self, property_path):
        property_path_clean = []
        property_path = property_path.replace("/","").replace(".","").split()
        if property_path[0] == "?this":
            property_path.pop(0)
        else:
            raise Exception("The property path should start with ?this")
        for p in property_path:
            property_path_clean.append((SH["property"], self.wordToURL(p.strip())))

        # Check final element is variable or constant IRI
        if property_path_clean[-1][1] == "?value":
            pass
        else:
            property_path_clean[-1] = (SH["hasValue"], property_path_clean[-1][1]) # TODO: To be fixed

        return property_path_clean

    def controlledClassReplace(self, c, list_type):
        return c # TODO: implement this

    def wordToURL(self, word):
        pass

    def checkType(self, url):
        pass

    def writeShapeToFile(self, file_name):
        self.SHACL.serialize(destination=file_name, format='turtle')

    def evaluate_file(self, args):
        # load the data
        self.dL = dataLoader(self.cm_file)

        # start the translation
        self.translate()

        # validate the SHACL
        shaclValidation = Graph()
        shaclValidation.parse("https://www.w3.org/ns/shacl-shacl")

        r = validate(self.SHACL, shacl_graph=shaclValidation)
        if not r[0]:
            print(r[2])

        if args.output_file:
            self.writeShapeToFile(args.output_file)
        else:
            self.writeShapeToFile(args.cm_file + ".shape.ttl")
        
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Translate Conceptual Mapping to SHACL')
    parser.add_argument("cm_file",  help='conceptual mapping file location', type=str)
    args = parser.parse_args()

    C2S = CMtoSHACL()
    C2S.evaluate_file(args.cm_file)