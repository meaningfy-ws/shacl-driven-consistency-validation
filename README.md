# CM2SHACL

A tool to generate SHACL shapes from Conceptual Mapping for RDF graphs validation.

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
$ python main.py -cm CM_FILE_LOCATION -o SHACL_PATH -cf CONFIGURATION_FILE -cv CONCEPTUAL_MAPPING_VERSION --close_shapes True
```
For example: 
```
$ python main.py -cm 'conceptual_mappings.xlsx' -cf 'config.ini' -cv 'Conceptual Mapping Version 1.0' -o 'shacl_output_v1.ttl' --close_shapes True
```

To validate RDF graph

```
$ python main.py --validation_shacl SHACL_PATH --validation_rdf RDF_PATH --validation_report OUTPUT_REPORT_PATH
```