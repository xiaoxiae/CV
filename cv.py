#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import shutil
from dataclasses import dataclass
from subprocess import DEVNULL, PIPE, Popen

import yaml
from markdown import markdown

parser = argparse.ArgumentParser(description="Generate a CV from a YAML file..")

parser.add_argument(
    "-i",
    "--input",
    help="The path to the input file (with extension), relative to this script's directory. Defaults to 'cv.yaml'.",
    default="cv.yaml",
)

parser.add_argument(
    "-o",
    "--output",
    help="The path to the output file (without extension), relative to this script's directory. Defaults to 'cv'.",
    default="cv",
)

parser.add_argument(
    "-c",
    "--cached",
    help="Copy the PDF directly from the cache folder if the contents didn't change. Only works when the --pdf flag is used.",
    action='store_true',
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

arguments = parser.parse_args()

YAML_NAME = arguments.input


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


def html(c: str):
    """Convert a string from Markdown to HTML."""
    return markdown(c)


@dataclass
class Node:
    content: str
    children: Optional[List[Node]] = None


    @classmethod
    def from_string(cls, string: str):
        return Node(None, cls.__from_list(string))

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

    def to_latex(self, information, depth=0):
        """Convert the node and all of its children to LaTeX."""
        LATEX_PRE = r"""
        \documentclass[10pt]{article}
        \usepackage{array, xcolor, lipsum, bibentry,titlesec,hyperref}
        \usepackage[margin={2.5cm,2cm}]{geometry}

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
        \newcolumntype{L}{>{\raggedleft}p{0.13\textwidth}}
        \newcolumntype{R}{p{0.8\textwidth}}
        \newcommand\VRule{\color{lightgray}\vrule width 0.5pt}

        \pagenumbering{gobble}

        \providecommand{\tightlist}{%
          \setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}

        \begin{document}

\topskip0pt
\vspace*{\fill} 

        \begin{center}
                {\scshape\Huge """ + information['name'] + r"""}
                \smallskip
                \smallskip

            \hrule

                \vspace*{0.2cm}

                {\large\textbf{Email:} \href{mailto:""" + information['email'] + r"""}{""" + information['email'] + r"""} \hfill
                \textbf{Website:} \href{https://""" + information['website'] + r"""}{""" + information['website'] + r"""}\hfill
                \textbf{GitHub:} \href{https://""" + information['github'] + r"""}{""" + information['github'] + r"""}}

                \vspace*{0.1cm}
        \end{center}

        \renewcommand{\arraystretch}{1.3}

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
        % 1/2 ratio for top and bottom space (it optically looks better)
        \vspace*{\fill}
        \vspace*{\fill}
        \end{document}
        """

        # when called from root
        if depth == 0:
            return (
                LATEX_PRE
                + "\n".join([child.to_latex(information, depth + 1) for child in self.children])
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
                    result += child.to_latex(information, depth + 1)
                return result + r" \end{tabular} \filbreak " + "\n"

            return result + "\n\smallskip\n" + latex(self.children[0].content)

        if depth == 2:
            result = r"\textit{" + latex(self.content) + "}"

            for child in self.children:
                result += " & " + child.to_latex(information, depth + 1) + r"\\"

            return result + "\n"

    def to_html(self, depth=0):
        """Convert the node and all of its children to HTML."""

        HTML_PRE = "<div class='cv'>"
        HTML_POST = "</div>"

        # when called from root
        if depth == 0:
            return (
                HTML_PRE
                + "\n".join([child.to_html(depth + 1) for child in self.children])
                + HTML_POST
            ).replace("--", "–")

        if self.children is None:
            return html(self.content)

        if depth == 1:
            result = f"<h3>{self.content}</h3>"

            if self.children[0].children is not None:
                result += "<table>" + "\n" + "<tbody>" + "\n"

                for child in self.children:
                    result += child.to_html(depth + 1)

                return result + "</tbody>" + "\n" + "</table>" + "\n"

            return result + "\n" + html(self.children[0].content)

        if depth == 2:
            result = f"""
            <tr>
                <td style='vertical-align: top; text-align: right;'><p><em>{self.content}</em></p></td>
                <td>{self.children[0].to_html(depth + 1)}</td>
            </tr>
            """

            for child in self.children[1:]:
                result += f"""
                    <tr>
                        <td></td>
                        <td>{child.to_html(depth + 1)}</td>
                    </tr>
                    """

            return result + "\n"


base = os.path.dirname(os.path.realpath(__file__))
cache_path = os.path.join(base, ".cv_cache")  # for TeX output

yaml_path = os.path.join(base, YAML_NAME)

with open(yaml_path, "r") as f:
    yaml_contents = f.read()
    result = yaml.safe_load(yaml_contents)

information = result[0]
root = Node.from_string(result[1:])

# generate a latex file when creating a PDF
if arguments.latex:
    with open(arguments.output + ".tex", "w") as f:
        f.write(root.to_latex(information))
    print("LaTeX CV generated!")

elif arguments.pdf:
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)

    # if we want to use the cached
    cached_yaml_path = os.path.join(cache_path, YAML_NAME)

    if os.path.exists(cached_yaml_path):
        with open(cached_yaml_path) as f:
            cached_yaml_contents = f.read()
    else:
        cached_yaml_contents = None

    # output tex
    latex_file_name = "cv.tex"
    latex_output_path = os.path.join(cache_path, latex_file_name)

    if not arguments.cached or yaml_contents != cached_yaml_contents:
        with open(latex_output_path, "w") as f:
            f.write(root.to_latex(information))

        cwd = os.getcwd()
        os.chdir(cache_path)
        Popen(["lualatex", latex_file_name], stdout=DEVNULL).communicate()
        os.chdir(cwd)

        # copy the yaml file so it can be cached
        shutil.copyfile(yaml_path, cached_yaml_path)
        print("PDF CV generated!")
    else:
        print("PDF CV cached!")

    shutil.copyfile(latex_output_path[:-3] + "pdf", arguments.output + ".pdf")

elif arguments.html:
    with open(arguments.output + ".html", "w") as f:
        f.write(root.to_html())
    print("HTML CV generated!")
