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


class CompInst(object):

    db = {}  # component database: key - name, val - object

    def db_add(self):
        assert self.name not in self.db
        self.db[self.name] = self

    def __init__(self, name, comp_ref, original_name, comp_value, pattern_name):
        self.name = name
        self.pins = {}
        self.comp_ref = comp_ref.val
        self.original_name = original_name.val
        self.comp_value = comp_value.val
        self.pattern_name = pattern_name.val
        self.db_add()

    def __repr__(self):
        return "CompInst(%r)" % self.__dict__

    @classmethod
    def set_pin_net(cls, cmp_name, pin, net_name):
        "Set net name for pin of the component"
        obj = cls.db[cmp_name]
        obj.pins[pin] = net_name


class Netlist(object):

    def __init__(self, name, *items):
        self.verbose = False
        self.name = name
        self.items = {}
        for item in items:
            ref = item.name
            if ref in self.items:
                raise KeyError("Net(%s)[%s] %s <-> %s" % (name, ref, self.items[ref], item))
            self.items[ref] = item

    def __str__(self):
        return "netlist(%s) -> %s" % (self.name, self.items)

    def comp_by_pin(self, vnet, npin):
        "Find component in given Net by pin"
        # if self.verbose:
        #    print("comp_by_pin(vnet %s)(npin %r)" % (vnet, npin))
        assert type(npin) == str
        rcmp = None
        for (comp_ref, pin) in vnet.nodes.items():
            if len(pin) == 1 and pin[0] == npin:
                if rcmp is not None:
                    # FIXME throw exception
                    print("Duplicated component in net", vnet)
                    sys.exit(os.EX_DATAERR)
                # rcmp = copy.copy(key)
                rcmp = comp_ref
        if rcmp is not None:
            rcmp = CompInst.db[rcmp]
        else:
            # FIXME throw exception
            print("No tranceiving component found in net %s" % vnet.name)
            sys.exit(os.EX_DATAERR)
        # if self.verbose:
        #     print(" -> %r" % rcmp)
        return rcmp

    def proc_1621(self, verb):
        self.verbose = verb
        vlist = []
        vdict = {}
        vlitc = {}
        for i in range(88):
            vlink = "VLINK_%02d" % i
            vnet = Net.get_by_name(vlink)
            if verb:
                print(vnet.name, vnet.nodes)
            vcmp = self.comp_by_pin(vnet, '1')
            pnet = self.items[vcmp.pins['3']]
            # if verb:
            #     print("L114: pnet is %r" % pnet)
            seta = 0
            clra = 0
            for comp_ref, pins in pnet.nodes.items():
                if len(pins) == 1 and pins[0] == '3':
                    l = CompInst.db[comp_ref].pins['2']
                    if re.fullmatch(r"LC\d{1,2}", l):
                        clra |= 1 << int(l[2:])
                    if re.fullmatch(r"~LC\d{1,2}", l):
                        seta |= 1 << int(l[3:])
            if seta & clra:
                print("Net: %s bitmask %03X %03X error" % (vnet.name, seta, clra))
                continue
            l = ""
            for j in range(11):
                if seta & (1 << j):
                    l = "1" + l
                    continue
                if clra & (1 << j):
                    l = "0" + l
                    continue
                l = "x" + l
            if verb:
                print("%s: 11'b%s" % (vnet.name, l))
            seta = 0
            for comp_ref, pins in vnet.nodes.items():
                if len(pins) == 1 and pins[0] == '2':
                    s = CompInst.db[comp_ref].pins['3']
                    if re.fullmatch(r"~TC\d", s):
                        seta |= 1 << int(s[3:])
            vlist.append(l)
            vdict[l] = i
            vlitc[l] = seta

        vlist.sort()
        print("mcp1621 arrays 0/1")
        for l in vlist:
            print("assign pl[%d] = cmp(lc, 11'b%s);" % (vdict[l], l))
        for l in vlist:
            print("11'b%s: tc = 7'x%02X;" % (l, vlitc[l]))

        vlist = []
        vdict = {}
        for i in range(100):
            vlink = "TLINK_%02d" % i
            vnet = Net.db.get(vlink, None)
            if vnet is None:
                print("Net %s not found in netlist" % vlink)
                sys.exit(os.EX_DATAERR)
            if verb:
                print(vnet.name, vnet.nodes)
            vcmp = self.comp_by_pin(vnet, '1')
            if vcmp is None:
                print("No tranceiving component found in net %s" % vnet.name)
                sys.exit(os.EX_DATAERR)
            if self.verbose:
                print("tcmp(name %s)" % vcmp.name)


class Node(namedtuple('node', ['comp_ref', 'pin'])):

    def __repr__(self):
        return '(node "%s" "%s")' % (self.comp_ref, self.pin)


class Net(object): # namedtuple('net', ['name', 'nodes'])):

    db = {}  # net database: key - name, val - object

    def db_add(self):
        assert self.name not in self.db
        self.db[self.name] = self

    @classmethod
    def get_by_name(cls, name):
        try:
            vnet = cls.db[name]
        except KeyError:
            print("Net %s not found in netlist" % name)
            sys.exit(os.EX_DATAERR)
        return vnet

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
            CompInst.set_pin_net(ref, node.pin, name)
        self.db_add()

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
        'node': Node,
        'compInst': CompInst,
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
    parser.add_argument("netfile",
                        # type=argparse.FileType('r'),
                        help="input netlist file in PCAD-2004 ASCII format")
    parser.add_argument("--arch",
                        choices=["cp1611", "cp1621"],
                        help="architecture used to translate the matrix",
                        default="cp1621")
    parser.add_argument("--verbose",
                        action="store_true",
                        help="architecture used to translate the matrix")
    return parser.parse_args()


def process_netlist(obj, arch, verbose=False):
    if arch == 'cp1611':
        # TODO: implement proc_1611
        obj.proc_1611(verbose)
    elif arch == 'cp1621':
        obj.proc_1621(verbose)
    else:
        raise RuntimeError("%s: unsupported arch" % arch)


if __name__ == '__main__':
    args = get_args()
    lex = parse_file(args.netfile)
    objs = []
    # parse and evaluate
    for tok in lex.stream():
        objs.append(eval(tok))
    # objs list contains 2 objects:
    # - asciiHeader
    # - netlist
    for obj in objs:
        if isinstance(obj, asciiHeader):
            # do nothing or print file header
            pass
        if isinstance(obj, Netlist):
            # print(type(obj))
            print("Parsed %d lines, %d component(s), %d net(s) " %
                  (lex.l_num, len(CompInst.db), len(Net.db)))
            process_netlist(obj, args.arch, args.verbose)
