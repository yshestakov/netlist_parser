#!/usr/bin/env python3
from __future__ import print_function
# https://norvig.com/lispy.html
# http://norvig.com/lispy2.html
from collections import namedtuple
import re
import sys
import os
import codecs
from argparse import ArgumentParser

class Symbol(str):        # A NetList Symbol is implemented as a Python str

    def __repr__(self):
        return 'Symbol(%s)' % self


Number = (int, float)     # A NetList Number is implemented as a Python int or float
Atom   = (Symbol, Number) # A NetList Atom is a Symbol or Number
List   = list             # A NetList List is implemented as a Python list
Exp    = (Atom, List)     # A NetList expression is an Atom or List
Env    = dict             # A NetList environment (defined below)
                          # is a mapping of {variable: value}
eof_object = Symbol('#<eof-object>') # Note: uninterned; can't be read

class asciiHeader(object):

    def __init__(self, ascii_ver, time_stamp, program, copyright,
                 file_author, header_str, file_units, guid_str):
        self.ascii_ver = ascii_ver
        self.time_stamp = time_stamp
        self.program = program
        self.copyright = copyright.val
        self.file_author = file_author.val
        self.header_str = header_str.val
        self.file_units = file_units.val
        self.guid_str = guid_str.val

    def __str__(self):
        return "asciiHeadear(%r)" % self.__dict__


class compInst(object):

    def __init__(self, name, comp_ref, original_name, comp_value, pattern_name):
        self.name = name
        self.comp_ref = comp_ref.val
        self.original_name = original_name.val
        self.comp_value = comp_value.val
        self.pattern_name = pattern_name.val

    def __repr__(self):
        return "compInst(%r)" % self.__dict__


class Netlist(object):

    def __init__(self, name, *items):
        self.name = name
        self.cmps = {}
        for item in items:
            ref = item.name
            if ref in self.cmps:
                raise KeyError("Net(%s)[%s] %s <-> %s" % (name, ref, self.cmps[ref], item))
            self.cmps[ref] = item

    def __str__(self):
        return "netlist(%s) -> %s" % (self.name, self.cmps)


class Net(object): # namedtuple('net', ['name', 'nodes'])):

    def __init__(self, name, *items):
        self.name = name
        self.nodes = {}
        for node in items:
            ref = node.comp_ref
            if ref in self.nodes:
                # raise KeyError("Net(%s)[%s] %s <-> %s" % (name, ref, self.nodes[ref], node.pin))
                self.nodes[ref].append(node.pin)
            else:
                self.nodes[ref] = [node.pin]

#    def __str__(self):
#        return "net(%s) -> %s" % (self.name, self.nodes)

    def __repr__(self):
        return "net(%s) -> %s" % (self.name, self.nodes)

scalarVal = namedtuple('scalar', ['val'])

def pcad_env() -> Env:
    "An environment with some PCAD symbols."
    env = Env()
    env.update({
        'asciiHeader': asciiHeader,
        'asciiVersion': namedtuple('asciiVersion', ['major', 'minor']),
        'timeStamp': namedtuple('timeStamp', ['yy','mm', 'dd', 'hour', 'min', 'sec']),
        'program': namedtuple('program', ['name', 'ver']),
        'copyright': scalarVal,
        'fileAuthor': scalarVal,
        'headerString': scalarVal,
        'fileUnits': scalarVal,
        'guidString': scalarVal,
        'Mil': Symbol,
        'net': Net,
        'netlist': Netlist,
        'node': namedtuple('node', ['comp_ref', 'pin']),
        'compInst': compInst,
        'compRef': namedtuple('compRef', ['val']),
        'originalName': scalarVal,
        'compValue': scalarVal,
        'patternName': scalarVal,
    })
    return env

global_env = pcad_env()
# print(repr(global_env))

def Sym(s, symbol_table={}):
    "Find or create unique Symbol entry for str s in symbol table."
    if s not in symbol_table:
        symbol_table[s] = Symbol(s)
    return symbol_table[s]
#------------------------------------------------------------------------
_quote = Sym('quote')
_quasiquote = Sym('quasiquote')

quotes = {"'": _quote, "`": _quasiquote}


class Lexer(object):
    """
    Lexer class
    It takes file object on input
    `next_token` func returns next token or eof_object
    """
    tokenizer = r'''\s*(,@|[('`,)]|"(?:[\\].|[^\\"])*"|;.*|[^\s('"`,;)]*)(.*)'''

    def __init__(self, f_in):
        self.f_in = f_in
        self.line = ''
        self.l_num = 0

    def next_token(self):
        "Return the next token, reading new text into line buffer if needed."
        while True:
            if self.line == '':
                self.l_num += 1
                self.line = self.f_in.readline()
                # print("next_token(l %d):r: %s" % (self.l_num, self.line))
            if self.line == '':
                return eof_object
            token, self.line = re.match(self.tokenizer, self.line).groups()
            # print("next_token(l %d):t: %r | %s" % (self.l_num, token, self.line))
            if token != '' and not token.startswith(';'):
                return token

    @staticmethod
    def atom(token: str) -> Atom:
        "Numbers become numbers; every other token is a symbol."
        if token[0] == '"':
            return token[1:-1]  # .decode('string_escape')
        try:
            return int(token)
        except ValueError:
            try:
                return float(token)
            except ValueError:
                return Sym(token)

    def read_stream(self):
        "Read a NetList expression from an input object (lexer)."
        def read_ahead(token):
            if '(' == token:
                L = []
                while True:
                    token = self.next_token()
                    if token == ')':
                        return L
                    else:
                        L.append(read_ahead(token))
            elif ')' == token:
                raise SyntaxError('unexpected )')
            elif token in quotes:
                return [quotes[token], self.read_stream()]
            elif token is eof_object:
                raise SyntaxError('unexpected EOF in list')
            else:
                return self.atom(token)
        # body of read:
        token1 = self.next_token()
        return eof_object if token1 is eof_object else read_ahead(token1)

    def __del__(self):
        "destructor, close input file"
        self.f_in.close()
        self.f_in = None

    def stream(self):
        while True:
            tok = self.read_stream()
            if tok == eof_object:
                return
            yield tok


def parse_file(fname: str) -> Exp:
    f_in = codecs.open(fname, encoding='cp1251', errors='replace')
    line = f_in.readline()
    # ACCEL_ASCII "R:\mcp1621a.net"
    m = re.search(r'''\s*(ACCEL_ASCII|PCAD_ASCII|TangoPRO_ASCII)\s*"(.*?)"''', line)
    if not m:
        raise SyntaxError("No header found: %s" % line)
    print("Process %s ..." % m.group(2))
    return Lexer(f_in)

def eval(x: Exp, env=global_env) -> Exp:
    "Evaluate an expression in an environment."
    # print(("eval %r" % x),)
    if isinstance(x, Symbol):  # variable reference
        return env[x]
    elif isinstance(x, str):
        return x
    elif isinstance(x, Number):  # constant number
        return x
    else:   # instanciate object
        try:
            cls = eval(x[0], env)
        except KeyError as ex:
            print("%r: %s" % (x, ex))
            raise ex
        # print("eval: cls is %r" % cls)
        args = [eval(arg, env) for arg in x[1:]]
        return cls(*args)


def get_args():
    parser = ArgumentParser(prog='mcp1621_proc')
    parser.add_argument('-f', dest='fname', required=True,
                        help='P-CAD *.net filename')
    return parser.parse_args()

if __name__ == '__main__':
    args = get_args()
    lex = parse_file(args.fname)
    objs = []
    for tok in lex.stream():
        objs.append(eval(tok))
    for obj in objs:
        if isinstance(obj, asciiHeader):
            # do nothing
            pass
        if isinstance(obj, Netlist):
            print(type(obj))
            # TODO: process netlist
