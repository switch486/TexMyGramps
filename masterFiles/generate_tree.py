# generate_tree.py

from collections import defaultdict
import logging

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
    parent|child|page
    """
    parts = line.strip().split("|")
    if len(parts) != 3:
        logger.warning(f"Skipping malformed line: {line.strip()}")
        return None

    parent, child, page = parts
    return parent.strip(), child.strip(), page.strip()


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
    def __init__(self, name):
        self.name = name
        self.page = None
        self.children = {}


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
    for parent, child, page in entries:
        p = get_node(parent)
        c = get_node(child)

        p.children[child] = c

        # assign page to child (last write wins if duplicates exist)
        c.page = page

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


def render_node(node):
    """
    Recursive forest rendering
    """

    label = escape_latex(node.name)

    if node.page:
        label = f"{label} \\newline \\small{{ str.{node.page}}}"

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
    grow=east,
    parent anchor=east,
    child anchor=west,
    align=center,
    l sep=15pt,
    s sep=10pt,
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
    forest_code = generate_forest(root)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(forest_code)

    logger.info(f"Written output to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()