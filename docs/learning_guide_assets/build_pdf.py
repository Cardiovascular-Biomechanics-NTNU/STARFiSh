"""Typeset the learning guide. This script does not run either solver."""
from pathlib import Path
import re, shutil, subprocess, tempfile
from markdown_it import MarkdownIt

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"docs/STARFISH_JAX_PORT_LEARNING_GUIDE.md"
ASSETS=ROOT/"docs/learning_guide_assets"
TARGET=ROOT/"docs/STARFISH_JAX_PORT_LEARNING_GUIDE.pdf"
MATH={}
def protect(m):
 key=f"GUIDEMATH{len(MATH):06d}END"
 display=m.group(1) is not None
 MATH[key]=(display,m.group(1) if display else m.group(2))
 return "\n\n"+key+"\n\n" if display else key
raw=SOURCE.read_text()
protected=re.sub(r"\\\[(.*?)\\\]|\\\((.*?)\\\)",protect,raw,flags=re.S)
tokens=MarkdownIt("commonmark").enable("table").parse(protected)
CHARS={"\\":r"\textbackslash{}","&":r"\&","%":r"\%","$":r"\$",
 "#":r"\#","_":r"\_","{":r"\{","}":r"\}","~":r"\textasciitilde{}",
 "^":r"\textasciicircum{}","“":r"\textquotedblleft{}","”":r"\textquotedblright{}",
 "²":r"\textsuperscript{2}","³":r"\textsuperscript{3}"}
def escape(s):return "".join(CHARS.get(c,c) for c in s)
def text(s):
 result=[]
 for part in re.split(r"(GUIDEMATH\d{6}END)",s):
  if part in MATH:
   display,body=MATH[part]
   result.append("\n\\begingroup\\small\n\\[\n"+body.strip()+"\n\\]\n\\endgroup\n" if display else r"\("+body+r"\)")
  else:result.append(escape(part))
 return "".join(result)
def code(s):
 s=escape(s)
 for sep in [r"\_","/","."]:s=s.replace(sep,sep+r"\allowbreak{}")
 return r"\texttt{"+s+"}"
def url(s):
 if not s.startswith(("http:","https:","#")):
  s=str((SOURCE.parent/s).resolve()) if not s.startswith("/") else s
 return s.replace("%",r"\%").replace("#",r"\#")
def inline(children):
 result=[]
 for t in children or []:
  kind=t.type
  if kind=="text":result.append(text(t.content))
  elif kind=="code_inline":result.append(code(t.content))
  elif kind=="softbreak":result.append(" ")
  elif kind=="hardbreak":result.append(r"\\")
  elif kind=="strong_open":result.append(r"\textbf{")
  elif kind=="strong_close":result.append("}")
  elif kind=="em_open":result.append(r"\emph{")
  elif kind=="em_close":result.append("}")
  elif kind=="link_open":result.append(r"\href{"+url(t.attrGet("href"))+"}{")
  elif kind=="link_close":result.append("}")
  elif kind=="image":
   p=(SOURCE.parent/t.attrGet("src")).resolve()
   if p.suffix==".svg":p=p.with_suffix(".pdf")
   result.append("\n\\begin{figure}[htbp]\n\\centering\n\\includegraphics[width=0.98\\linewidth]{"+str(p)+"}\n\\caption{"+escape(t.content)+"}\n\\end{figure}\n")
  elif kind.startswith("html_"):result.append(escape(re.sub("<[^>]+>","",t.content)))
  else:raise ValueError(f"Unknown inline token: {kind}")
 return "".join(result)
def table(block):
 rows=[];row=[];cell=""
 for t in block:
  if t.type=="tr_open":row=[]
  elif t.type in ("th_open","td_open"):cell=""
  elif t.type=="inline":cell+=inline(t.children)
  elif t.type in ("th_close","td_close"):row.append(cell)
  elif t.type=="tr_close":rows.append(row)
 n=len(rows[0]);width=.98/n
 spec="".join(r">{\raggedright\arraybackslash}p{\dimexpr"+f"{width:.5f}"+r"\linewidth-2\tabcolsep\relax}" for _ in range(n))
 head=" & ".join(r"\textbf{"+x+"}" for x in rows[0])+r" \\"+"\n"
 result=["\n\\begingroup\\footnotesize\n\\setlength{\\tabcolsep}{4pt}\n\\begin{longtable}{"+spec+"}\n\\toprule\n",head,"\\midrule\n\\endfirsthead\n",head,"\\midrule\n\\endhead\n\\bottomrule\n\\endfoot\n"]
 for row in rows[1:]:result.append(" & ".join(row)+r" \\"+"\n")
 result.append("\\end{longtable}\n\\endgroup\n")
 return "".join(result)
out=[];i=0
while i<len(tokens):
 t=tokens[i];kind=t.type
 if kind=="heading_open":
  level=int(t.tag[1:]);heading=inline(tokens[i+1].children)
  if level==2:out.append("\\clearpage\n\\section{"+heading+"}\n")
  elif level==3:out.append("\\subsection{"+heading+"}\n")
  elif level>3:out.append("\\subsubsection{"+heading+"}\n")
  i+=3;continue
 if kind=="table_open":
  j=i
  while tokens[j].type!="table_close":j+=1
  out.append(table(tokens[i:j+1]));i=j+1;continue
 if kind=="paragraph_open":pass
 elif kind=="paragraph_close":out.append("\n\n")
 elif kind=="inline":out.append(inline(t.children))
 elif kind=="fence":out.append("\n\\begin{lstlisting}\n"+t.content.replace("“",'"').replace("”",'"')+"\\end{lstlisting}\n")
 elif kind=="bullet_list_open":out.append("\n\\begin{itemize}\n")
 elif kind=="bullet_list_close":out.append("\\end{itemize}\n")
 elif kind=="ordered_list_open":out.append("\n\\begin{enumerate}\n")
 elif kind=="ordered_list_close":out.append("\\end{enumerate}\n")
 elif kind=="list_item_open":out.append("\\item ")
 elif kind=="list_item_close":out.append("\n")
 elif kind=="blockquote_open":out.append("\n\\begin{quote}\n")
 elif kind=="blockquote_close":out.append("\\end{quote}\n")
 elif kind=="hr":out.append("\n\\medskip\\hrule\\medskip\n")
 elif kind=="html_block":out.append(escape(re.sub("<[^>]+>","",t.content)))
 else:raise ValueError(f"Unknown block token: {kind}")
 i+=1
preamble=r"""\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\usepackage[margin=22mm]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{graphicx,xcolor}
\usepackage{array,longtable,booktabs,listings}
\usepackage{hyperref}
\definecolor{navy}{HTML}{18334D}
\definecolor{linkblue}{HTML}{176B91}
\definecolor{codebg}{HTML}{F2F5F7}
\hypersetup{colorlinks=true,linkcolor=linkblue,urlcolor=linkblue,
 pdftitle={STARFiSh and Python CRIMSON: Mathematics and JAX Porting Guide},
 pdfauthor={Learning guide and implementation analysis},
 bookmarksnumbered=false,breaklinks=true}
\urlstyle{same}
\setcounter{secnumdepth}{0}
\setcounter{tocdepth}{1}
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt plus 1pt}
\setlength{\emergencystretch}{3em}
\sloppy
\allowdisplaybreaks[1]
\lstset{basicstyle=\ttfamily\footnotesize,breaklines=true,
 breakatwhitespace=false,columns=fullflexible,keepspaces=true,
 showstringspaces=false,backgroundcolor=\color{codebg},
 frame=single,rulecolor=\color{black!15},xleftmargin=5pt,xrightmargin=5pt,
 aboveskip=8pt,belowskip=8pt}
\title{\color{navy}\Huge STARFiSh and Python CRIMSON\\[8pt]
 \Large Mathematics and JAX Porting Guide}
\author{A detailed learning guide from equations to implementation}
\date{19 October 2026}
\begin{document}
\maketitle
\vspace{12pt}
\begin{center}
\large Starting from units, arrays, derivatives and conservation laws\\[5pt]
\normalsize Current STARFiSh formulas, direct Python-netlist coupling,\\
and the changes needed for a JAX numerical backend.
\end{center}
\vfill
\begin{quote}
This document distinguishes physical models, inspected implementation behavior,
and proposed porting designs. The numerical solvers were not modified.
\end{quote}
\clearpage
\tableofcontents
\clearpage
"""
latex=preamble+"".join(out)+"\n\\end{document}\n"
(ASSETS/"STARFISH_JAX_PORT_LEARNING_GUIDE.tex").write_text(latex)
with tempfile.TemporaryDirectory(prefix="starfish-jax-guide-") as folder:
 build=Path(folder);(build/"guide.tex").write_text(latex)
 for attempt in range(3):
  proc=subprocess.run(["pdflatex","-interaction=nonstopmode","-halt-on-error","guide.tex"],cwd=build,text=True,capture_output=True)
  if proc.returncode:
   print(proc.stdout[-7000:]);raise SystemExit(proc.returncode)
 log=(build/"guide.log").read_text(errors="replace")
 shutil.copy2(build/"guide.pdf",TARGET)
 (ASSETS/"typesetting_report.txt").write_text("\n".join(line for line in log.splitlines() if any(x in line for x in ["Overfull","Underfull","Warning"]))+"\n")
print(f"Rendered {TARGET}")
print(f"Math expressions: {len(MATH)}; bytes: {TARGET.stat().st_size:,}")

