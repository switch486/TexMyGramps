# build.py

import subprocess
import sys

def run(cmd):
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        sys.exit(result.returncode)

def main():
    # 1st pass (generate .dat with page numbers)
    run("tectonic masterDocument/main.tex")

    # generate tree from mytoc.dat
    run("python masterDocument/generate_tree.py")

    # 2nd pass (include generated tree)
    run("tectonic masterDocument/main.tex")

if __name__ == "__main__":
    main()