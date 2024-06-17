"""
Utiles functions for the CM2SHACL translation
"""

import json
import requests
import re
from collections import Counter
from rdflib import Graph, URIRef, Literal, BNode, RDF, RDFS, Namespace
SHACL = Namespace("http://www.w3.org/ns/shacl#")

def json_load(json_name):
    """
    Load a json file from a URL or a local file
    """
    if re.match(r'https?://', str(json_name)):
        return requests.get(json_name).json()
    with open(json_name, 'r', encoding='utf-8') as f:
        return json.load(f)
