#!/usr/bin/python3

import pygraphviz

def vlan(net, png_path):
    G = pygraphviz.AGraph(strict=False, directed=True)
    G.layout(prog='dot')
    G.draw(png_path, prog='dot')


