#!/usr/bin/env python3.4
"""
Write symtable_data_test.go
"""

import sys
import ast
import subprocess
import dis
from symtable import symtable

# FIXME test errors too

inp = [
    ('''1''', "eval"),
    ('''a*b*c''', "eval"),
    ('''def fn(): pass''', "exec"),
    ('''def fn(a,b):\n e=1\n return a*b*c*d*e''', "exec"),
    ('''def fn(a,b):\n def nested(c,d):\n  return a*b*c*d*e''', "exec"),
    ('''\
def fn(a:"a",*arg:"arg",b:"b"=1,c:"c"=2,**kwargs:"kw") -> "ret":
    def fn(A,b):
        e=1
        return a*arg*b*c*kwargs*A*e*glob''', "exec"),
    ('''\
def fn(a):
    global b
    b = a''', "exec"),
    ('''\
def fn(a):
    b = 6
    global b
    b = a''', "exec"),
    ('''\
def outer():
   x = 1
   def inner():
       nonlocal x
       x = 2''', "exec"),
    ('''\
def outer():
   def inner():
       nonlocal x
       x = 2''', "exec", SyntaxError),
    # FIXME need with x as y
]

def dump_bool(b):
    return ("true" if b else "false")

def dump_strings(ss):
    return "[]string{"+",".join([ '"%s"' % s for s in ss ])+"}"

# Scope numbers to names (from symtable.h)
SCOPES = {
    1: "scopeLocal",
    2: "scopeGlobalExplicit",
    3: "scopeGlobalImplicit",
    4: "scopeFree",
    5: "scopeCell",
}

#def-use flags to names (from symtable.h)
DEF_FLAGS = (
    ("defGlobal", 1),      # global stmt
    ("defLocal", 2),       # assignment in code block
    ("defParam", 2<<1),    # formal parameter
    ("defNonlocal", 2<<2), # nonlocal stmt
    ("defUse", 2<<3),      # name is used
    ("defFree", 2<<4),     # name used but not defined in nested block
    ("defFreeClass", 2<<5),# free variable from class's method
    ("defImport", 2<<6),   # assignment occurred via import
)

#opt flags flags to names (from symtable.h)
OPT_FLAGS = (
    ("optImportStar", 1),
    ("optTopLevel", 2),
)

BLOCK_TYPES = {
    "function": "FunctionBlock",
    "class": "ClassBlock",
    "module": "ModuleBlock",
}

def dump_flags(flag_bits, flags_dict):
    """Dump the bits in flag_bits using the flags_dict"""
    flags = []
    for name, mask in flags_dict:
        if (flag_bits & mask) != 0:
            flags.append(name)
    if not flags:
        flags = ["0"]
    return "|".join(flags)

def dump_symtable(st):
    """Dump the symtable"""
    out = "&SymTable{\n"
    out += 'Type:%s,\n' % BLOCK_TYPES[st.get_type()] # Return the type of the symbol table. Possible values are 'class', 'module', and 'function'.
    out += 'Name:"%s",\n' % st.get_name() # Return the table’s name. This is the name of the class if the table is for a class, the name of the function if the table is for a function, or 'top' if the table is global (get_type() returns 'module').

    out += 'Lineno:%s,\n' % st.get_lineno() # Return the number of the first line in the block this table represents.
    out += 'Unoptimized:%s,\n' % dump_flags(st._table.optimized, OPT_FLAGS) # Return False if the locals in this table can be optimized.
    out += 'Nested:%s,\n' % dump_bool(st.is_nested()) # Return True if the block is a nested class or function.
    #out += 'Exec:%s,\n' % dump_bool(st.has_exec()) # Return True if the block uses exec.
    #out += 'ImportStar:%s,\n' % dump_bool(st.has_import_star()) # Return True if the block uses a starred from-import.
    out += 'Varnames:%s,\n' % dump_strings(st._table.varnames)
    out += 'Symbols: Symbols{\n'
    children = dict()
    for name in st.get_identifiers():
        s = st.lookup(name)
        out += '"%s":%s,\n' % (name, dump_symbol(s))
        ns = s.get_namespaces()
        if len(ns) == 0:
            pass
        elif len(ns) == 1:
            children[name] = ns[0]
        else:
            raise AssertionError("More than one namespace")
    out += '},\n'
    out += 'Children:map[string]*SymTable{\n'
    for name, symtable in children.items():
        out += '"%s":%s,\n' % (name, dump_symtable(symtable))
    out += '},\n'
    out += "}"
    return out

def dump_symbol(s):
    """Dump a symbol"""
    #class symtable.Symbol
    # An entry in a SymbolTable corresponding to an identifier in the source. The constructor is not public.
    out = "Symbol{\n"
    out += 'Flags:%s,\n' % dump_flags(s._Symbol__flags, DEF_FLAGS)
    scope = SCOPES.get(s._Symbol__scope, "scopeUnknown")
    out += 'Scope:%s,\n' % scope
    out += "}"
    return out

def escape(x):
    """Encode strings with backslashes for python/go"""
    return x.replace('\\', "\\\\").replace('"', r'\"').replace("\n", r'\n').replace("\t", r'\t')

def main():
    """Write symtable_data_test.go"""
    path = "symtable_data_test.go"
    out = ["""// Test data generated by make_symtable_test.py - do not edit

package compile

import (
"github.com/ncw/gpython/py"
)

var symtableTestData = []struct {
in   string
mode string // exec, eval or single
out  *SymTable
exceptionType *py.Type
errString string
}{"""]
    for x in inp:
        source, mode = x[:2]
        if len(x) > 2:
            exc = x[2]
            try:
                table = symtable(source, "<string>", mode)
            except exc as e:
                error = e.msg
            else:
                raise ValueError("Expecting exception %s" % exc)
            dumped_symtable = "nil"
            gostring = "nil"
            exc_name = "py.%s" % exc.__name__
        else:
            table = symtable(source, "<string>", mode)
            exc_name = "nil"
            error = ""
            dumped_symtable = dump_symtable(table)
        out.append('{"%s", "%s", %s, %s, "%s"},' % (escape(source), mode, dumped_symtable, exc_name, escape(error)))
    out.append("}\n")
    print("Writing %s" % path)
    with open(path, "w") as f:
        f.write("\n".join(out))
        f.write("\n")
    subprocess.check_call(["gofmt", "-w", path])

if __name__ == "__main__":
    main()
