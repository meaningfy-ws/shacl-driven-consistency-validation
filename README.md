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
$ python main.py CM_FILE_LOCATION 
```

Or you can specify the location for storing the generated SHACL shapes

```
$ python main.py CM_FILE_LOCATION -o SHACL_PATH
```
