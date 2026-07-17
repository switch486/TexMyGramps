# generate_tree.py

from collections import defaultdict
import logging
import re

INPUT_FILE = "output/mytoc.dat"
OUTPUT_FILE = "output/generated_tree.tex"

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


def parse_line(line):
    """
    expected format:
    key|parent|child|birth|death|page
    """
    parts = line.strip().split("|")
    if len(parts) != 6:
        logger.warning(f"Skipping malformed line: {line.strip()}")
        return None

    key, parent, child, birth, death, page = parts
    return key.strip(), parent.strip(), child.strip(), birth.strip(), death.strip(), page.strip()


def escape_latex(s):
    return (
        s.replace("\\", r"\textbackslash ")
         .replace("&", r"\&")
         .replace("%", r"\%")
         .replace("$", r"\$")
         .replace("#", r"\#")
         .replace("_", r"\_")
         .replace("{", r"\{")
         .replace("}", r"\}")
    )


class Node:
    def __init__(self, name, birth="", death=""):
        self.name = name
        self.birth = birth
        self.death = death
        self.page = None
        self.children = {}
        self.path_list = []


def build_tree(entries):
    """
    Builds a tree from parent-child relations.
    Also infers roots automatically.
    """

    logger.info(f"Building tree from {len(entries)} relations")

    nodes = {}
    children_set = set()

    def get_node(name):
        if name not in nodes:
            nodes[name] = Node(name)
        return nodes[name]

    # build graph
    for key, parent, child, birth, death, page in entries:
        p = get_node(parent)
        c = get_node(child)

        p.children[child] = c

        # assign page to child (last write wins if duplicates exist)
        c.key = key
        c.page = page
        c.birth = birth
        c.death = death

        children_set.add(child)

    # find roots (nodes that are never children)
    all_nodes = set(nodes.keys())
    roots = list(all_nodes - children_set)

    logger.info(f"Detected roots: {roots}")

    # create artificial root if needed
    if len(roots) == 1:
        root = nodes[roots[0]]
    else:
        root = Node("Table of Contents")
        for r in roots:
            root.children[r] = nodes[r]

    return root


def set_paths(node, current_path):
    """Set the path list for each node from root."""
    node.path_list = current_path + [node.name]
    for child in node.children.values():
        set_paths(child, node.path_list)


def generate_headers(root):
    """Generate headers for each page showing the path from root."""
    headers = {}
    
    def traverse(node):
        if node.page:
            path_str = " $\\leftarrow$ ".join(escape_latex(name) for name in node.path_list)
            headers[node.key] = path_str
        for child in node.children.values():
            traverse(child)
    
    traverse(root)
    return headers


def render_node(node):
    """
    Recursive forest rendering
    """

    label = " ".join(f"\\bfseries{{{word}}}" for word in escape_latex(node.name).split())
    label = label.replace(" ", "\\\\")

    if node.page:
        label = (
            label
            + f"\\\\\\small{{{node.birth}}}"
            + f"  \\small{{{node.death}}}"
            + f"\\\\\\hyperlink{{page.{node.page}}}{{str.{node.page}}}"
        )

    if not node.children:
        return f"[{label}]"

    children_tex = "\n".join(
        render_node(child) for child in node.children.values()
    )

    return f"[{label}\n{children_tex}\n]"


def generate_forest(root):
    logger.info("Generating LaTeX forest output")

    return "\n".join([
"""\\begin{forest}
for tree={
    font=\\footnotesize,
    text width=2.35cm,
    grow=east,
    parent anchor=east,
    child anchor=west,
    anchor=east,
    align=left,
    l sep=15pt,
    s sep=0pt,
    edge path={
        \\noexpand\\path[\\forestoption{edge}]
        (!u.parent anchor) -- +(5pt,0pt) |- (.child anchor)\\forestoption{edge label};
    }
}""",
        render_node(root),
        r"\end{forest}"
    ])


def main():
    logger.info(f"Reading input file: {INPUT_FILE}")

    entries = []

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parsed = parse_line(line)
                if parsed:
                    entries.append(parsed)
    except FileNotFoundError:
        logger.error(f"Input file not found: {INPUT_FILE}")
        return

    logger.info(f"Parsed {len(entries)} edges")

    root = build_tree(entries)
    set_paths(root, [])
    headers = generate_headers(root)
    forest_code = generate_forest(root)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(forest_code)

    headers_file = "output/tree_headers.tex"
    with open(headers_file, "w", encoding="utf-8") as f:
        for macro_name, header in headers.items():
            header_newline = header + " \\vspace{0.5em}"
            f.write(f"\\def\\{macro_name}{{{header_newline}}}\n")

    logger.info(f"Written output to {OUTPUT_FILE}")
    logger.info(f"Written headers to {headers_file}")


if __name__ == "__main__":
    main()