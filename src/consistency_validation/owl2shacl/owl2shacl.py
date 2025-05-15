import rdflib
import requests


def translateFromUrl(ontology, output_file="output.ttl"):


    onto = {"ontologies": [ontology]}
    astrea_url = 'https://astrea.linkeddata.es/api/shacl/url'
    shacl_shape = requests.post(astrea_url, json = onto)

    graph = rdflib.Graph().parse(data=shacl_shape.text, format="turtle")
    graph = correctSHACL(graph)
    graph.serialize(destination=output_file, format='turtle')


def translateFromFile(ontology, output_file="output.ttl"):
    """
    Translate an ontology from a file to SHACL shapes using the ASTREA API.
    :param ontology: The path to the ontology file.
    :param output_file: The path to the output SHACL file.
    :return: None
    """

    print("Starting translation SHACL shapes for OWL")
    ontology = rdflib.Graph().parse(ontology, format="turtle").serialize(format="turtle")

    onto = {
    "ontology": ontology,
    "serialisation": "TURTLE"
    }
    astrea_url = 'https://astrea.linkeddata.es/api/shacl/document'
    shacl_shape = requests.post(astrea_url, json = onto)
    graph = rdflib.Graph().parse(data=shacl_shape.text, format="turtle")
    graph = correctSHACL(graph)
    graph.serialize(destination=output_file, format='turtle')


def correctSHACL(shape):
   
    shaclNS = rdflib.Namespace('http://www.w3.org/ns/shacl#')
    checkList = [shaclNS.nodeKind, shaclNS.datatype, shaclNS.minCount, shaclNS.maxCount, shaclNS.minExclusive, shaclNS.maxExclusive, shaclNS.minInclusive, shaclNS.maxInclusive, shaclNS.minLength, shaclNS.maxLength, shaclNS.pattern, shaclNS.flags, shaclNS.languageIn, shaclNS.uniqueLang, shaclNS.qualifiedMinCount, shaclNS.qualifiedMaxCount]
    checkLiteralList = [shaclNS.minCount, shaclNS.maxCount, shaclNS.minExclusive, shaclNS.maxExclusive, shaclNS.minInclusive, shaclNS.maxInclusive, shaclNS.minLength, shaclNS.maxLength, shaclNS.qualifiedMinCount, shaclNS.qualifiedMaxCount]

    identifiers = []
    for s in shape.subjects(rdflib.RDF.type,shaclNS.NodeShape):
        identifiers.append(s)
    for s in shape.subjects(rdflib.RDF.type,shaclNS.PropertyShape):
        identifiers.append(s)
    
    for identifier in identifiers:
        for check in checkList:
            number_value = shape.value(identifier, check)

    for constraint in checkList:
        for s in identifiers:
            temp = []
            for value in shape.objects(s,constraint):
                if (constraint in checkLiteralList):
                    shape.remove((s,constraint,value))
                    value = rdflib.Literal(int(value))
                    shape.add((s,constraint,value))
                temp.append(value)
            if len(temp) > 1:
                for value in temp:
                    shape.remove((s,constraint,value))
    
    for s, p, o in shape.triples((None, None, shaclNS.PropertyShape)):
        path = shape.value(s, shaclNS.path)
        if not path:
            shape.remove((s, None, shaclNS.PropertyShape))
            # for s2, p2, o2 in shape.triples((s, None, None)):
            #     shape.remove((s2, p2, o2))
            # for s2, p2, o2 in shape.triples((None, None, s)):
            #     shape.remove((s2, p2, o2))
    return shape