# SHACL-driven Consistency Validator

🛠️ To perform SHACL-driven consistency validation that systematically detects inconsistencies among the artefacts involved in the TED Mapping Workflow. 

It directly support the consistency validation among ontologies, conceptual mappings, and RML mapping rules.
---

## 📦 Data Sources

The Consistency Validator is developed and applied on two major variants of the TED RDF mapping projects:
- [Standard Forms repository](https://github.com/meaningfy-ws/ted-rdf-mapping-standard-forms)
- [eForms repository](https://github.com/meaningfy-ws/ted-rdf-mapping-eforms)

The `data/` folder in this repository contains mapping suites extracted from these projects,  
specifically focusing on the Conceptual Mapping (CM) files and RDF artefacts (RML mappings and OWL ontologies).

---

## ⚙️ Prerequisites

Install required dependencies with:

```bash
pip install -r requirements.txt
```

---
## 🧩 SHACL Extraction Modules

The Consistency Validator currently supports SHACL extraction from multiple artefact types using the following modules:

- **Conceptual Mapping (CM)**:  
  ➔ Extracted using [CM2SHACL](https://github.com/meaningfy-ws/cm2shacl), a dedicated module for translating Conceptual Mapping rules into SHACL shapes.

- **RML Mappings**:  
  ➔ Extracted using modified [RML2SHACL](https://github.com/RMLio/RML2SHACL), a tool that rewrites RML mappings into SHACL shapes for consistency validation.

- **OWL Ontologies**:  
  ➔ Extracted using [Astrea](https://github.com/oeg-upm/astrea).  
  One option is use the [SCOOP-UI platform](https://demos.citius.usc.es/scoop/) which integrates Astrea for a more user-friendly SHACL generation experience from OWL ontologies.

Each artefact type has its corresponding SHACL extraction module, enabling automated consistency checking across multiple layers and sources.

---
## 🧩 Command-line Arguments

```bash
usage: main.py [-h] [-c CM] [-v CM_VERSION] [-f CONFIG_FILE] [-cs CM_SHACL] [-r RML] [-rs RML_SHACL] [-w OWL] [-ws OWL_SHACL] [-wc OWL_CACHE] [-o OUTPUT]

SHACL-driven Consistency Validation

options:
  -h, --help            show this help message and exit
  -c CM, --cm CM        Conceptual Mapping (CM) Excel file (.xlsx)
  -v CM_VERSION, --cm_version CM_VERSION
                        CM version as specified in the config file
  -f CONFIG_FILE, --config_file CONFIG_FILE
                        ath to configuration file (default: config.ini)
  -cs CM_SHACL, --cm_shacl CM_SHACL
                        Path to SHACL shapes from CM. If not available, specify a target path to generate and store them.
  -r RML, --rml RML     RML file or folder path
  -rs RML_SHACL, --rml_shacl RML_SHACL
                        Path to SHACL shapes from RML. If not available, specify a target path to generate and store them.
  -w OWL, --owl OWL     OWL ontology file (.ttl or .owl)
  -ws OWL_SHACL, --owl_shacl OWL_SHACL
                        Path to SHACL shapes from OWL. If not available, specify a target path to generate and store them.
  -wc OWL_CACHE, --owl_cache OWL_CACHE
                        Path to existing OWL SHACL cache file (if available)
  -o OUTPUT, --output OUTPUT
                        Path to output JSON consistency validation report
```

---

## 🚀 Usage

### 1. Validate Consistency Across Artefacts

Specify SHACL files directly if available, or provide CM/RML/OWL artefacts corresponding with the location that you want to place the generated SHACL shapes:

```bash
python main.py --cm CM_FILE --cm_shacl CM_SHACL_FILE --rml RML_FILE_OR_FOLDER --rml_shacl RML_SHACL_FILE --owl OWL_FILE --owl_shacl OWL_SHACL_FILE --output OUTPUT_JSON
```

If an OWL SHACL cache is available, you can provide it to skip OWL processing:

```bash
python main.py --cm CM_FILE --rml RML_FILE_OR_FOLDER --owl_cache OWL_CACHE_FILE --output OUTPUT_JSON
```

---

## 📋 Examples

🔹 Validate using artefacts:

```bash
python main.py --owl_cache 'evaluation/standardForms/ontology/cache.pkl' --cm 'data/standardForms/package_F03/transformation/conceptual_mappings.xlsx' --cm_shacl 'cm_shacl.ttl' --rml 'data/standardForms/package_F03/transformation/mappings' --rml_shacl 'rml_shacl.ttl' --output 'report.json'
```

🔹 Validate using pre-generated SHACL shapes:

```bash
python main.py --cm_shacl 'cm_shacl.ttl' --rml_shacl 'rml_shacl.ttl' --owl_shacl 'owl_shacl.ttl' --output 'report.json'
```

---

## 🧪 Evaluation

We evaluated the effectiveness of the Consistency Validator by applying it to the TED mapping suites and measuring its ability to detect inconsistencies across CM, RML, and OWL artefacts.

- **Reproduce validation results:**:

```bash
python evaluation/evaluation.py
```

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
