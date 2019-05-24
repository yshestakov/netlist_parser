#!/usr/bin/env python3
from __future__ import print_function
# https://norvig.com/lispy.html
# http://norvig.com/lispy2.html
import re

class Symbol(str):        # A NetList Symbol is implemented as a Python str
    pass
Number = (int, float)     # A NetList Number is implemented as a Python int or float
Atom   = (Symbol, Number) # A NetList Atom is a Symbol or Number
List   = list             # A NetList List is implemented as a Python list
Exp    = (Atom, List)     # A NetList expression is an Atom or List
Env    = dict             # A NetList environment (defined below)
                          # is a mapping of {variable: value}
eof_object = Symbol('#<eof-object>') # Note: uninterned; can't be read

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
    # \s*(,@|[('`,)]|
    # tokenizer = r'''\s*("(?:[\\].|[^\\"])*"|;.*|[^\s('"`,;)]*)(.*)'''
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
                # FIXME
                if self.l_num > 100:
                    raise RuntimeError()
                return eof_object
            token, self.line = re.match(self.tokenizer, self.line).groups()
            # print("next_token(l %d):t: %r | %s" % (self.l_num, token, self.line))
            if token != '' and not token.startswith(';'):
                return token


def atom(token: str) -> Atom:
    "Numbers become numbers; every other token is a symbol."
    if token[0] == '"':
        return token[1:-1]  # .decode('string_escape')
    try: return int(token)
    except ValueError:
        try: return float(token)
        except ValueError:
            return Symbol(token)


def read_lex_stream(lexer):
    "Read a NetList expression from an input object (lexer)."
    def read_ahead(token):
        if '(' == token:
            L = []
            while True:
                token = lexer.next_token()
                if token == ')': return L
                else: L.append(read_ahead(token))
        elif ')' == token:
            raise SyntaxError('unexpected )')
        elif token in quotes:
            return [quotes[token], read(inport)]
        elif token is eof_object:
            raise SyntaxError('unexpected EOF in list')
        else:
            return atom(token)
    # body of read:
    token1 = lexer.next_token()
    return eof_object if token1 is eof_object else read_ahead(token1)


if __name__ == '__main__':
    with open('data/03.net', 'r') as f_in:
        # ret = tokenize(fi.read())
        lex = Lexer(f_in)
        while True:
            tok = read_lex_stream(lex)
            print(tok)
            if tok == eof_object:
                break
