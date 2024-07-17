from src.cm2shacl import CMtoSHACL
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Translate Conceptual Mapping to SHACL')
    parser.add_argument("cm_file",  help='conceptual mapping file location', type=str)
    parser.add_argument("-o", "--output_file", help='output file location', type=str, default=None)
    args = parser.parse_args()

    C2S = CMtoSHACL()
    C2S.evaluate_file(args)