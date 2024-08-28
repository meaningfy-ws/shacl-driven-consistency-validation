import os
from rdflib import Graph, URIRef
import pyshacl
import subprocess
import time

def shacl_analysis(results_graph):
    violations = 0
    for s, p, o in results_graph:
        if URIRef("http://www.w3.org/ns/shacl#ValidationResult") == o:
            violations += 1
    return violations

start_time = time.time()
package_list = ["package_F03"]
results_dict = {}
for package in package_list:
    results_dict[package] = {}

    rdf_path = os.path.join(os.getcwd(), f'evaluation/{package}/rdf')
    cm_file = os.path.join(os.getcwd(), f'evaluation/{package}/conceptual_mappings.xlsx')
    shacl_output_file = os.path.join(os.getcwd(), f'evaluation/{package}/shacl_output.ttl')
 
    # # Run the called script with arguments to generate SHACL shapes from Conceptual Mappings
    subprocess.run(['python', './main.py', cm_file, '-o', shacl_output_file])

    shacl_g = Graph().parse(shacl_output_file, format='turtle')

    # Iterate through all RDF graphs in subfolders of the package
    subfolders = [f.path for f in os.scandir(rdf_path) if f.is_dir()]
    for subfolder in subfolders:
        subfolder_name = os.path.basename(subfolder)
        results_dict[package][subfolder_name] = {}
        rdffolders = [f.path for f in os.scandir(subfolder) if f.is_dir()]
        for rdffolder in rdffolders:
            # get file under this folder and ends with .ttl
            rdffolder_name = os.path.basename(rdffolder)
            results_dict[package][subfolder_name][rdffolder_name] = {}
            files = [f.path for f in os.scandir(rdffolder) if f.is_file() and f.name.endswith('.ttl')]
            for file in files:
                print(f"Start validating {file}")
                data_g = Graph().parse(file, format='turtle')
                conforms, results_graph, results_text = pyshacl.validate(data_g, shacl_graph=shacl_g)
                # save the validation report to a file
                validation_report_file = os.path.join(rdffolder, 'shacl_validation_report.ttl')
                results_graph.serialize(destination=validation_report_file, format='turtle')
                violations = shacl_analysis(results_graph)
                results_dict[package][subfolder_name][rdffolder_name][os.path.basename(file)] = {"conforms":conforms, "violations":violations} 

                # exit()
# Write the results to a file
results_file = os.path.join(os.getcwd(), 'evaluation/evaluation_results.json')
with open(results_file, 'w') as f:
    f.write(str(results_dict))



end_time = time.time()
print(f"Total time: {end_time - start_time}")


