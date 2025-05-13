# SHACL-driven Cross-layer Consistency Validator

A SHACL-driven Cross-layer Consistency Validation framework that leverages SHACL as a unified data profile to detect inconsistencies among various modeling assets involved in the TED mapping workflow.


## Prerequisite

Install the required dependencies:

```
$ pip install -r requirements.txt
```

## Usage

To translate Conceptual Mapping file to SHACL shapes:

```
$ python main.py -cm CM_FILE_LOCATION 
```

Or you can specify the location for storing the generated SHACL shapes

```
$ python main.py -cm CM_FILE_LOCATION -o SHACL_PATH -cf CONFIGURATION_FILE -cv CONCEPTUAL_MAPPING_VERSION
```
You can specify whether want to close the generated SHACL shapes

```
$ python main.py -cm CM_FILE_LOCATION -o SHACL_PATH -cf CONFIGURATION_FILE -cv CONCEPTUAL_MAPPING_VERSION 
```
For example: 
```
$ python main.py -cm 'conceptual_mappings.xlsx' -cf 'config.ini' -cv 'Conceptual Mapping Version 1.0' -o 'shacl_output_v1.ttl'
```

To validate RDF graph

```
$ python main.py --validation_shacl SHACL_PATH --validation_rdf RDF_PATH --validation_report OUTPUT_REPORT_PATH
```

## Data Analysis
The summary statistics of mapping suites in the Standard Forms and eForms repositories, 
including the average number of conceptual mapping rules, 
RML Triple Maps and Predicate-Object Maps, and classes and properties 
defined in OWL (O), Conceptual Mapping (C), and RML (R) 
are located at data/report.txt. 

To reproduce the statistics result, run the following command:

```
$ python data_analysis.py 
```