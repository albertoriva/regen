#!/usr/bin/python

import sys
import csv
import os.path
import subprocess

DEFAULTCSS = """
BODY {
  background: lightgrey;
  font-family: arial;
  font-size: 12pt;
  line-height: 150%;
  margin: 0px;
}
TABLE.main {
  width: 90%;
  border-collapse: separate;
  border-spacing: 10px;
}
TD.section {
  background: white;
  border: 2px solid #444444;
  border-radius: 4px;
  padding: 10px;
  page-break-after: always;
}
.caption {
  font-style: italic;
}
.filebox {
  text-align: left;
  border: 2px solid #222222;
  background: #ffe4b5;
  padding: 5px;
  margin: 10px;
}
TABLE.datatable {
  min-width: 50%;
  margin: 10px;
  border: 2px solid #222222;
  border-collapse: collapse;
}
TH.datatable {
  padding: 5px;
  background: orange;
  font-weight: bold;
  border-bottom: 2px solid #222222;
}
TD.datatable {
  padding: 5px;
  border-bottom: 1px solid #222222;
  border-left: 1px dotted #222222;
}

"""

def getCommand(line):
    p = line.find(" ")
    if p > 0:
        return line[:p], line[p+1:].strip()
    else:
        return line.strip(), ""

def splitBar(line):
    parts = [ s.strip() for s in line.split("|") ]
    if len(parts) == 1:
        parts = parts + [""]
    return parts

def nameAndProps(line):
    name = ""
    props = {}
    parts = [ s.strip() for s in line.split("|") ]
    name = parts[0]
    for s in parts[1:]:
        if "=" in s:
            p = s.find("=")
            props[s[:p]] = s[p+1:]
        else:
            props[s] = True
    return name, props

def pget(key, props):
    if key in props:
        return props[key]
    else:
        return None

def printBytes(b):
    # Return a string containing the number b formatted as a number of
    # bytes, or kilobytes, or megabytes, or gigabytes, as appropriate.
    if b < 1024:
        return "{} bytes".format(b)
    b = b / 1024.0
    if b < 1024:
        return "{:.2f} kB".format(b)
    b = b / 1024.0
    if b < 1024:
        return "{:.2f} MB".format(b)
    b = b / 1024.0
    return "{:.2f} GB".format(b)

def shell(command, *args):
    cmd = command.format(*args)
    try:
        return subprocess.check_output(cmd, shell=True).rstrip("\n")
    except subprocess.CalledProcessError as cpe:
        return cpe.output.rstrip("\n")

def fileLines(filename):
    r = shell("wc -l " + filename)
    p = r.find(" ")
    if p > 0:
        return r[:p]
    else:
        return None

class MultiReader(object):
    infiles = []
    nfiles = 0

    _iterator = None
    _current = 0
    _stream = None
    
    def __init__(self, infiles):
        self.infiles = infiles
        self.nfiles = len(infiles)

    def __enter__(self):
        self._stream = open(self.infiles[0])
        return self

    def __exit__(self, type, value, traceback):
        if self._stream:
            self._stream.close()

    def __iter__(self):
        self._iterator = MultiReaderIterator(self)
        return self._iterator

    def next(self):
        return self._iterator.__next__()

class MultiReaderIterator:
    parent = None

    def __init__(self, parent):
        self.parent = parent

    def next(self):
        return self.__next__()
        
    def __next__(self):
        while True:
            w = self.parent._stream.readline()
            if w:
                return w
            else:
                self.parent._stream.close()
                self.parent._current += 1
                if self.parent._current == self.parent.nfiles:
                    raise StopIteration
                else:
                    self.parent._stream = open(self.parent.infiles[self.parent._current])
            
class ReGen(object):
    # User-supplied
    infiles = []
    outfile = "index.html"
    cssfiles = []
    jsfiles = []
    title = "Report"
    banner = ""

    # Configuration
    thumbsize = 300
    
    # Methods
    _mtable = {}
    
    # Runtime
    _out = sys.stdout
    _css = ""
    _sceneIdx = 0
    _figIdx = 0
    _tableIdx = 0
    _inScene = False
    _inPar = False
    
    def __init__(self):
        self.infiles = []
        self._mtable = {".title": self.set_title,
                        ".banner": self.set_banner,
                        ".css": self.add_css,
                        ".js": self.add_js,
                        ".start": self.start,
                        ".include": self.include,
                        ".inc": self.include,
                        ".section": self.section,
                        ".sec": self.section,
                        ".p": self.openPar,
                        ".par": self.openPar,
                        ".img": self.image,
                        ".image": self.image,
                        ".file": self.file,
                        ".table": self.table
        }
        
    def parseArgs(self, args):
        prev = ""
        for a in args:
            if prev == "-o":
                self.outfile = a
                prev = ""
            elif prev == "-c":
                self.cssfiles.append(a)
                prev = ""
            elif prev == "-j":
                self.jsfiles.append(a)
                prev = ""
            elif prev == "-t":
                self.title = a
                prev = ""
            elif prev == "-b":
                self.banner = a
                prev = ""
            elif a in ["-o", "-c", "-j", "-t", "-b"]:
                prev = a
            else:
                self.infiles.append(a)
        if self.outfile == "-":
            self.outfile = "/dev/stdout"
        if not self.infiles:
            self.infiles.append("/dev/stdin")

    def run(self):
        with open(self.outfile, "w") as out:
            self._out = out
            with MultiReader(self.infiles) as m:
                for line in m:
                    if line[0] == '.':
                        key, rest = getCommand(line)
                        if key in self._mtable:
                            meth = self._mtable[key]
                            meth(rest)
                        else:
                            sys.stderr.write("Warning: unknown command {}\n".format(key))
                    else:
                        self._out.write(line)
            self.closing()
                        
            
    # Methods

    def openPar(self, pclass):
        self.closePar()
        if pclass:
            self._out.write("<P class='{}'>".format(pclass))
        else:
            self._out.write("<P>")
        self._inPar = True
        
    def closePar(self):
        if self._inPar:
            self._out.write("</P>\n")
            self._inPar = False
    
    def set_title(self, line):
        self.title = line

    def set_banner(self, line):
        self.banner = line

    def add_css(self, line):
        self.cssfiles.append(line)

    def add_js(self, line):
        self.jsfiles.append(line)

    def start(self, line):
        self.preamble()

    def include(self, filename):
        if os.path.isfile(filename):
            with open(filename, "r") as f:
                self._out.write(f.read())

    def section(self, title):
        if self._inScene:
            self._out.write("</TD></TR>\n\n")
        self._inScene = True
        self._sceneIdx += 1
        self._out.write("<TR><TD class='section'><big><A name='sec{}'>{}. {}</A></big><BR>\n".format(self._sceneIdx, self._sceneIdx, title))

    def image(self, line):
        self.closePar()
        imgfile, props = nameAndProps(line)
        self._out.write("<CENTER><A href='{}' target='_blank'><IMG src='{}' height={} border=1></A>\n".format(imgfile, imgfile, self.thumbsize))
        if "desc" in props:
            self._figIdx += 1
            self._out.write("<BR><span class='caption'><b>Figure {}.</b> {}</span>".format(self._figIdx, props["desc"]))
        self._out.write("</CENTER>\n")

    def file(self, line):
        self.closePar()
        filename, props = nameAndProps(line)
        desc = pget("desc", props)
        lines = pget("lines", props)
        if lines:
            c = fileLines(filename)
        self._out.write("""<CENTER><DIV class='filebox'><b>File</b>: <A href='{}'>{}</A><BR>
<b>Size</b>: {}<BR>
{}
{}
</DIV></CENTER>\n""".format(filename, filename, printBytes(os.path.getsize(filename)),
                            "<b>Description:</b> {}<BR>".format(desc) if desc else "",
                            "<b>Lines:</b> {}".format(c) if desc else ""))

    def table(self, line):
        self.closePar()
        filename, props = nameAndProps(line)
        desc = pget("desc", props)
        header = pget("header", props)
        maxlines = pget("maxl", props) or 5
        maxlines = int(maxlines)
        ncols = 0
        self._out.write("<CENTER><TABLE class='datatable'>\n")
        with open(filename, "r") as f:
            c = csv.reader(f, delimiter='\t')
            if header:
                hline = c.next()
                self._out.write("<THEAD><TR class='datatable'>")
                self._out.write("".join([ "<TH class='datatable'>" + h + "</TH>" for h in hline ]))
                self._out.write("</TR></THEAD>\n<TBODY>\n")
            nl = 0
            for line in c:
                ncols = max(ncols, len(line))
                self._out.write("<TR>" + "".join([ "<TD class='datatable'>" + h + "</TD>" for h in line ]) + "</TR>\n")
                nl += 1
                if nl == maxlines:
                    break
        self._out.write("<TR><TD colspan='{}'><b>Download:</b> <A href='{}' target='_blank'>{}</A><BR><b>Displaying:</b> Top {} rows</TR></TR>".format(ncols, filename, filename, maxlines))
        self._out.write("</TBODY></TABLE>")
        if "desc" in props:
            self._tableIdx += 1
            self._out.write("<span class='caption'><b>Table {}.</b> {}</span><BR>".format(self._tableIdx, props["desc"]))
        self._out.write("</CENTER>\n")
        
    # HTML generation
    
    def preamble(self):
        out = self._out
        out.write("""<!DOCTYPE html>
<html>
  <head>
    <title>{}</title>
    <style type='text/css'>
""".format(self.title))
        if self.cssfiles:
            for cssfile in self.cssfiles:
                if os.path.isfile(cssfile):
                    with open(self.cssfile, "r") as f:
                        out.write(f.read())
        else:
            out.write(DEFAULTCSS)
        out.write("""
    </style>
  </head>
  <body>            
{}
    <center>
      <h1>{}</h1>
      <table class='main'>
""".format(self.banner, self.title))

    def closing(self):
        out = self._out
        if self._inScene:
            out.write("</TD></TR>\n\n")
        out.write("""
      </table>
    </center>
  </body>
</html>
""")

if __name__ == "__main__":
    args = sys.argv[1:]
    RG = ReGen()
    RG.parseArgs(args)
    RG.run()
        
"""
Directives:

.title <title>
.css <cssfile>
.banner <html>
.start
.include <htmlfile>
.h1, .h2, ...
.section <section title>
.p text
.image filename|description
.file filename|description
.table csvfile|caption=...|nrows=...|header={True|False}

"""
