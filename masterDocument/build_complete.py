# build.py

import subprocess
import sys
import os

def run(cmd):
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        sys.exit(result.returncode)

def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    main_file = f"main_{stage}.tex" if stage else "main.tex"

    if not os.path.isfile(main_file):
        sys.stderr.write(f"ERROR: expected main tex file not found: {main_file}\n")
        sys.exit(1)

    run("mkdir -p ./output")

    # 1st pass (generate .dat with page numbers)
    run(f"tectonic -o output/ {main_file}")

    # generate tree from mytoc.dat
    run("python generate_tree.py")

    # 2nd pass (include generated tree)
    run(f"tectonic -o output/ {main_file}")

if __name__ == "__main__":
    main()