#!/usr/bin/env python

def tokenize(chars: str) -> list:
    "Convert a string of characters into a list of tokens."
    return chars.replace('(', ' ( ').replace(')', ' ) ').split()

if __name__ == '__main__':
    with open('data/01.net', 'r') as fi:
        ret = tokenize(fi.read())
        print(repr(ret))
