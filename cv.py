#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import os
import re
from dataclasses import dataclass
from subprocess import DEVNULL, PIPE, Popen
from typing import *

import yaml
from markdown import markdown

parser = argparse.ArgumentParser(description="Generate a CV from a YAML file..")

parser.add_argument(
    "out",
    help="The path to the file, without extension. Defaults to 'cv'.",
    default="cv",
)

group = parser.add_mutually_exclusive_group(required=True)

group.add_argument(
    "--latex", help="Make the output a LaTeX file.", action="store_true",
)

group.add_argument(
    "--pdf", help="Make the output a PDF (from LaTeX).", action="store_true",
)

group.add_argument(
    "--html", help="Make the output an HTML.", action="store_true",
)

parser.add_argument(
    "-i", "--ignore-cache", help="Ignore the cache file.", action="store_true",
)

arguments = parser.parse_args()


def get_string_hashsum(string: str):
    """Generate a SHA-256 hashsum of the given string."""
    return hashlib.sha256(string.encode()).hexdigest()


def html(c: str):
    """Convert a string from Markdown to HTML."""
    markdown(c)


def latex(c: str):
    """Convert a string from Markdown to LaTeX."""
    result = []
    for line in re.split("<br>", c.replace("\n\n", "\n\n\\vspace{0.5em}")):
        result.append(
            Popen(["pandoc", "--to", "latex"], stdout=PIPE, stdin=PIPE)
            .communicate(input=line.encode())[0]
            .decode()
            .strip()
        )
    return r" \newline ".join(result)


@dataclass
class Node:
    content: str
    children: Optional[List[Node]] = None

    @classmethod
    def from_file(cls, path: str):

        with open(path, "r") as f:
            result = yaml.safe_load(f.read())

        return Node(None, cls.__from_list(result))

    @classmethod
    def __from_list(cls, l: list):
        """Return a list of nodes, given a nested list."""
        result = []
        i = 0
        while i < len(l):
            n = Node(l[i])
            if i + 1 == len(l) or isinstance(l[i + 1], str):
                i += 1
            else:
                n.children = cls.__from_list(l[i + 1])
                i += 2
            result.append(n)

        return result

    def pprint(self, indent=0):
        """Debug method for printing out the node structure."""
        print("\t" * indent + (self.content or "ROOT"))
        for child in self.children or []:
            child.pprint(indent + 1)

    def leaf_count(self) -> int:
        """Return the number of leafs of the node."""
        if self.children is None:
            return 1
        return sum([child.leaf_count() for child in self.children])

    def hashsum(self):
        """Return a hashsum of the contents of the node and its children."""
        return get_string_hashsum(
            (self.content or "")
            + "{"
            + "-".join([child.hashsum() for child in (self.children or [])])
            + "}"
        )

    def to_latex(self, depth=0):
        LATEX_PRE = r"""
        \documentclass[10pt]{article}
        \usepackage{array, xcolor, lipsum, bibentry,titlesec,hyperref}
        \usepackage[margin=3cm]{geometry}

        \titleformat{\section}{\scshape\fontsize{17pt}{19.6}\selectfont}{\thesection}{0em}{}

        \hypersetup{
             colorlinks = true,
             linkcolor = black,
             anchorcolor = black,
             citecolor = black,
             filecolor = black,
             urlcolor = black
        }

        \definecolor{lightgray}{gray}{0.8}
        \newcolumntype{L}{>{\raggedleft}p{0.14\textwidth}}
        \newcolumntype{R}{p{0.786\textwidth}}
        \newcommand\VRule{\color{lightgray}\vrule width 0.5pt}

        \pagenumbering{gobble}

        \providecommand{\tightlist}{%
          \setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}

        \begin{document}

        \begin{center}
                {\scshape\Huge Tomáš Sláma}
                \smallskip
                \smallskip

            \hrule

                \vspace*{0.2cm}

                {\large
                \textbf{Email:} \href{mailto:tomas@slama.dev}{tomas@slama.dev} \hfill
                \textbf{Website:} \href{https://slama.dev}{slama.dev}\hfill
                \textbf{GitHub:} \href{https://github.com/xiaoxiae}{github.com/xiaoxiae}
                }

                \vspace*{0.1cm}
        \end{center}

        \renewcommand{\arraystretch}{1.5}

        \hypersetup{
             colorlinks = true,
             linkcolor = gray,
             anchorcolor = gray,
             citecolor = gray,
             filecolor = gray,
             urlcolor = gray
        }
        """

        LATEX_POST = r"""
        \end{document}
        """

        # when called from root
        if depth == 0:
            return (
                LATEX_PRE
                + "\n".join([child.to_latex(depth + 1) for child in self.children])
                + LATEX_POST
            )

        if self.children is None:
            return latex(self.content)

        if depth == 1:
            result = f"""
            \\section*{{{self.content}}}
            \\vspace{{-0.8em}}
            \\hrule
            """

            if self.children[0].children is not None:
                result += r"\begin{tabular}{L!{\VRule}R}" + "\n"
                for child in self.children:
                    result += child.to_latex(depth + 1)
                return result + r" \end{tabular} \filbreak " + "\n"
            else:
                return result + "\n\smallskip\n" + latex(self.children[0].content)

        elif depth == 2:
            result = r"\textit{" + latex(self.content) + "}"

            for child in self.children:
                result += " & " + child.to_latex(depth + 1) + r"\\"

        return result + "\n"

    def to_html(self, depth=0, max_depth=3, tr=True):
        """Get the node string associated with the node."""

        if self.children is None:
            return f"""
            {'<tr>' if tr else ''}
            <td class="cv-content-cell" colspan="{max_depth - depth}">
                {html(self.content)}
            </td>
            {'</tr>' if tr else ''}
            """
        elif depth == 0:
            return f"""
            <tr>
                <td rowspan="{self.leaf_count()}" class="cv-primary-group">
                    <p><span>{self.content}</span></p>
                </td>
                {self.children[0].to_html(depth + 1, tr=False)}
            </tr>
            {"".join([child.to_html(depth + 1) for child in self.children[1:]])}
            """
        elif depth == 1:
            return f"""
            {'<tr>' if tr else ''}
            <td class="cv-secondary-group">
              <p><span>{self.content}</span></p>
            </td>
            {"".join([child.to_html(depth + 1, tr=False) for child in self.children])}
            {'</tr>' if tr else ''}
            """


base = os.path.dirname(os.path.realpath(__file__))
cache_path = os.path.join(base, f".cv")  # for TeX output and cache stuff
hashsum_path = os.path.join(cache_path, "hashsum")

root = Node.from_file(os.path.join(base, "cv.yaml"))

if os.path.exists(hashsum_path) and not arguments.ignore_cache:
    with open(hashsum_path, "r") as f:
        contents = f.read().strip()

    if contents == root.hashsum():
        print("No changes.")
        quit()


# generate a latex file when creating a PDF
if arguments.latex:
    with open(arguments.out + ".tex", "w") as f:
        f.write(root.to_latex())
    print("LaTeX CV generated!")

elif arguments.pdf:
    # cache
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)

    # output tex
    latex_file_name = os.path.basename(arguments.out) + ".tex"
    latex_output_path = os.path.join(cache_path, latex_file_name)
    with open(latex_output_path, "w") as f:
        f.write(root.to_latex())

    cwd = os.getcwd()
    os.chdir(cache_path)
    Popen(["lualatex", latex_file_name], stdout=DEVNULL).communicate()
    os.chdir(cwd)

    os.rename(latex_output_path[:-3] + "pdf", arguments.out + ".pdf")
    print("PDF CV generated!")

elif arguments.html:
    print("TODO!")
