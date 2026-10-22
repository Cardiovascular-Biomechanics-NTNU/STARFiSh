"""Typeset the closed-loop plan with native LaTeX equations; run no solvers.

Rebuild: python3 -B docs/netlist_closed_loop_assets/build_pdf.py
Requires markdown-it-py and the local pdflatex packages used below.
"""
from pathlib import Path
import hashlib, json, re, shutil, subprocess, tempfile
from markdown_it import MarkdownIt

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"docs/netlist_closed_loop_implementation_plan.md"
ASSETS=Path(__file__).resolve().parent
TARGET=SOURCE.with_suffix(".pdf")
MATH={}
CODE_MATH={symbol:symbol for symbol in (
 "n","h^n","z^n","x","A_c","f","u","p","q","P_v","Q_v","R_i",
 "w_i","k_i","H_p","H_q","A","B","F","G_p","G_q","J_p","J_q",
 "d_i","i","j","l","m","n+1","s","e","w","(p_0)_i",
 "(1, 2)","(12, 11)","(29, 35)","q = 0","F = I")}
CODE_MATH.update({
 "dt":r"\Delta t","theta^n":r"\theta^n","sigma":r"\sigma",
 "sigma_i":r"\sigma_i","eta":r"\eta","eta_i":r"\eta_i",
 "alpha_m":r"\alpha_m","alpha*dt":r"\alpha\Delta t",
 "Hop_i":r"\mathrm{Hop}_i","dP":r"\Delta P","dQ":r"\Delta Q",
 "q_i = sigma_i * Q_v,i":r"q_i=\sigma_i Q_{v,i}",
 "q_component,i = eta_i * q_i":r"q_{\mathrm{component},i}=\eta_i q_i",
 "alfi = 1":r"\mathrm{alfi}=1","alfi=1":r"\mathrm{alfi}=1",
 "rtol = 5e-11":r"\mathrm{rtol}=5\times10^{-11}",
 "atol = 1e-8 Pa":r"\mathrm{atol}=10^{-8}\,\mathrm{Pa}",
 "1e-12 m³":r"10^{-12}\,\mathrm{m}^3",
 "1e-12 m³/s":r"10^{-12}\,\mathrm{m}^3/\mathrm{s}",
 "1e-14 m²":r"10^{-14}\,\mathrm{m}^2",
 "(dp_dq, Hop) = (10, 19)":r"(\mathrm{dp\_dq},\mathrm{Hop})=(10,19)",
})
CODE_MATH_COUNT=0
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
 "²":r"\textsuperscript{2}","³":r"\textsuperscript{3}",
 "·":r"\ensuremath{\cdot}","→":r"\ensuremath{\rightarrow}","–":"--","—":"---"}
def escape(s):return "".join(CHARS.get(c,c) for c in s)
def text(s):
 result=[]
 for part in re.split(r"(GUIDEMATH\d{6}END)",s):
  if part in MATH:
   display,body=MATH[part]
   result.append("\n\\nopagebreak[3]\n\\[\n"+body.strip()+"\n\\]\n" if display else r"\("+body+r"\)")
  else:result.append(escape(part))
 return "".join(result)
def code(s):
 global CODE_MATH_COUNT
 if s in CODE_MATH:
  CODE_MATH_COUNT+=1
  return r"\("+CODE_MATH[s]+r"\)"
 chunks=re.split(r"(?<=[a-z])(?=[A-Z])|(?<=[/_.:])",s)
 return r"\texttt{"+r"\allowbreak{}".join(escape(chunk) for chunk in chunks)+"}"
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
 n=len(rows[0])
 widths={2:(.36,.64),3:(.29,.30,.41),4:(.18,.35,.33,.14)}[n]
 header=" ".join(rows[0])
 if "Symbol" in header:widths=(.19,.81)
 elif "Contribution" in header:widths=(.60,.20,.20)
 elif "Physical surface" in header:widths=(.23,.23,.30,.24)
 spec="".join(r">{\raggedright\arraybackslash}p{\dimexpr"+f"{width:.5f}"+r"\linewidth-2\tabcolsep\relax}" for width in widths)
 head=" & ".join(r"\textbf{"+x+"}" for x in rows[0])+r" \\"+"\n"
 result=["\n\\begingroup\\footnotesize\n\\setlength{\\tabcolsep}{4pt}\n\\renewcommand{\\arraystretch}{1.17}\n\\begin{longtable}{"+spec+"}\n\\toprule\n",head,"\\midrule\n\\endfirsthead\n",head,"\\midrule\n\\endhead\n\\bottomrule\n\\endfoot\n"]
 for row in rows[1:]:result.append(" & ".join(row)+r" \\[3pt]"+"\n")
 result.append("\\end{longtable}\n\\endgroup\n")
 return "".join(result)
DIAGRAM=r"""
\begin{center}
\begin{tikzpicture}[>=stealth,line width=.8pt,
 box/.style={draw=navy!60,rounded corners=3pt,fill=navy!4,
 minimum width=56mm,minimum height=15mm,align=center,font=\small}]
\node[box] (heart) at (0,0) {Heart boundary circuit\\\footnotesize 0D netlist};
\node[box] (vessels) at (8,0) {Starfish vessel network\\\footnotesize 1D domain};
\node[box] (outlets) at (8,-2.4) {Outlet boundary circuits\\\footnotesize 0D netlists};
\node[box] (return) at (0,-2.4) {Shared downstream return\\\footnotesize 0D netlist};
\draw[->,navy] (heart) -- (vessels);
\draw[->,navy] (vessels) -- (outlets);
\draw[->,navy] (outlets) -- (return);
\draw[->,navy] (return) -- (heart);
\end{tikzpicture}
\end{center}
"""
out=[];i=0
while i<len(tokens):
 t=tokens[i];kind=t.type
 if kind=="heading_open":
  level=int(t.tag[1:]);heading=inline(tokens[i+1].children)
  if tokens[i+1].content=="Contents":
   i+=3
   while i<len(tokens) and tokens[i].type!="heading_open":i+=1
   continue
  if level==2:
   if tokens[i+1].content.startswith("9. "):out.append("\\clearpage\n")
   out.append("\\Needspace{6\\baselineskip}\n\\section{"+heading+"}\n")
  elif level==3:
   lines=22 if tokens[i+1].content.startswith("8.2 ") else 5
   out.append("\\Needspace{"+str(lines)+"\\baselineskip}\n\\subsection{"+heading+"}\n")
  elif level>3:out.append("\\subsubsection{"+heading+"}\n")
  i+=3;continue
 if kind=="table_open":
  j=i
  while tokens[j].type!="table_close":j+=1
  out.append(table(tokens[i:j+1]));i=j+1;continue
 if kind=="paragraph_open":pass
 elif kind=="paragraph_close":out.append("\n\n")
 elif kind=="inline":out.append(inline(t.children))
 elif kind=="fence":
  if t.info.strip()=="mermaid":out.append(DIAGRAM)
  else:
   language="[language=Python]" if t.info.strip()=="python" else ""
   out.append("\n\\begin{lstlisting}"+language+"\n"+t.content+"\\end{lstlisting}\n")
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
\usepackage[margin=22mm,headheight=14pt]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{graphicx,xcolor}
\usepackage{array,longtable,booktabs,listings}
\usepackage{tikz,microtype,enumitem,needspace,titlesec,fancyhdr}
\usepackage{hyperref}
\definecolor{navy}{HTML}{18334D}
\definecolor{linkblue}{HTML}{176B91}
\definecolor{codebg}{HTML}{F2F5F7}
\hypersetup{colorlinks=true,linkcolor=linkblue,urlcolor=linkblue,
 pdftitle={Closed-loop CRIMSON netlist integration in Starfish},
 pdfsubject={Mathematics and proposed NumPy implementation},
 bookmarksnumbered=false,breaklinks=true}
\urlstyle{same}
\setcounter{secnumdepth}{0}
\setcounter{tocdepth}{1}
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt plus 1pt}
\setlength{\emergencystretch}{3em}
\sloppy
\allowdisplaybreaks[1]
\setlist{leftmargin=*,itemsep=3pt,topsep=4pt,parsep=2pt}
\titleformat{\section}{\Large\sffamily\bfseries\color{navy}}{}{0pt}{}
\titleformat{\subsection}{\large\sffamily\bfseries\color{navy}}{}{0pt}{}
\titlespacing*{\section}{0pt}{18pt}{8pt}
\titlespacing*{\subsection}{0pt}{12pt}{5pt}
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\small\sffamily\color{navy}STARFISH / CRIMSON}
\fancyhead[R]{\small\sffamily Closed-loop implementation plan}
\fancyfoot[C]{\small\thepage}
\renewcommand{\headrulewidth}{.3pt}
\lstset{basicstyle=\ttfamily\footnotesize,breaklines=true,
 breakatwhitespace=false,columns=fullflexible,keepspaces=true,
 showstringspaces=false,backgroundcolor=\color{codebg},
 frame=single,rulecolor=\color{black!15},xleftmargin=5pt,xrightmargin=5pt,
 aboveskip=8pt,belowskip=8pt,upquote=true}
\begin{document}
\begin{titlepage}
\vspace*{28mm}
{\sffamily\color{navy}\Huge\bfseries Closed-loop CRIMSON\\[6pt]
netlist integration\\[6pt]in Starfish\par}
\vspace{12mm}
{\sffamily\Large Mathematics and proposed implementation\par}
\vspace{6mm}
{\large NumPy/reference backend\par}
\vspace{5mm}
20 October 2026
\vfill
\hrule\vspace{5mm}
\textbf{Planning document.} Source findings, proposed equations, software
interfaces, lifecycle changes and validation gates are identified explicitly.
This export does not implement the proposed runtime.
\vspace{5mm}
\end{titlepage}
\tableofcontents
\clearpage
"""
latex=preamble+"".join(out)+"\n\\end{document}\n"
(ASSETS/(SOURCE.stem+".tex")).write_text(latex)
with tempfile.TemporaryDirectory(prefix="starfish-closed-loop-pdf-") as folder:
 build=Path(folder);(build/"guide.tex").write_text(latex)
 for attempt in range(3):
  proc=subprocess.run(["pdflatex","-interaction=nonstopmode","-halt-on-error","guide.tex"],cwd=build,text=True,capture_output=True)
  if proc.returncode:
   (ASSETS/"typesetting_error.log").write_text(proc.stdout)
   print(proc.stdout[-7000:]);raise SystemExit(proc.returncode)
 log=(build/"guide.log").read_text(errors="replace")
 shutil.copy2(build/"guide.pdf",TARGET)
 (ASSETS/"typesetting_report.txt").write_text("\n".join(line for line in log.splitlines() if any(x in line for x in ["Overfull","Underfull","Warning"]))+"\n")
report={"source":str(SOURCE.relative_to(ROOT)),
 "source_sha256":hashlib.sha256(raw.encode()).hexdigest(),
 "pdf":str(TARGET.relative_to(ROOT)),"pdf_bytes":TARGET.stat().st_size,
 "display_math_blocks":sum(display for display,_ in MATH.values()),
 "inline_math_expressions":sum(not display for display,_ in MATH.values()),
 "mathematical_code_spans_typeset":CODE_MATH_COUNT,
 "engine":"pdflatex / Computer Modern mathematics",
 "rebuild":"python3 -B docs/netlist_closed_loop_assets/build_pdf.py"}
(ASSETS/"export_manifest.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))

