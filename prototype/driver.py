#!/usr/bin/python3

from argparse import ArgumentParser
import config
import graph
import nsdi
import os
import prensdi

def simplify_path(path):
    simple = [path[0]]
    for vertex in path[1:]:
        router = vertex.split(':')[0]
        if simple[-1] != router:
            simple += [router]
    return simple 

def check_paths(net, graphs, verbose=False):
    for p in net.paths:
        g = graphs[(p.origin, p.endpoint)]
        found, hops = g.has_path(p.failset)
        print("%s" % (p))
        if (found):
            bestpath, bestsign = g.tpvp(verbose, p.failset)
            if (bestpath is not None):
                print('\t'+str(bestsign))
                print('\t'+'\n\t'.join(bestpath))
                if (simplify_path(bestpath) != p.expected):
                    print("ERROR: path should be [%s] but is [%s]" %
                            ('>'.join(p.expected), 
                            '>'.join(simplify_path(bestpath))))
            else:
                print('\tNo path')
        else:
            print('\tNo path')
            if (found != p.exists):
                print("ERROR: path should%s exist but does%s exist" %
                        (("" if p.exists else "n't"), ("" if found else "n't")))

def main():
    # Parse arguments
    arg_parser = ArgumentParser(description='Tiramisu prototype')
    arg_parser.add_argument('-json', dest='json_path', action='store',
            required=True, help='Path to network json')
    arg_parser.add_argument('-render', dest='render_path', action='store',
            required=True, help='Path to render graphs')
    arg_parser.add_argument('-rules', dest='rules', action='store',
            help='Rules to follow',
            choices=["nsdi", "prensdi", "nsditpg", "prensdimod", "nsdimod"])
    arg_parser.add_argument('-paths', dest='paths', action='store_true',
            help='Check paths')
    arg_parser.add_argument('-verbose', dest='verbose', action='store_true',
            help='Verbose output')
    arg_parser.add_argument('-contract', dest='contract', action='store_true',
            help='Conduct edge-contraction on TPG')
    settings = arg_parser.parse_args()
    print("Settings: %s" % settings)

    net = config.Network.load(settings.json_path)
    print(net)

    # Generate physical and layer 2
    phy = graph.Physical(net)
    phy.render(os.path.join(settings.render_path, 'physical.png'))
    l2 = graph.Layer2(net)
    l2.render(os.path.join(settings.render_path, 'layer2.png'))
    ospf = graph.Ospf(net, l2)
    ospf.render(os.path.join(settings.render_path, 'ospf.png'))
    bgp = graph.Bgp(net)
    bgp.render(os.path.join(settings.render_path, 'bgp.png'))
    combined = graph.Combined(net, l2)
    combined.render(os.path.join(settings.render_path, 'combined.png'))


    # Determine subnets
    subnets = set()
    for router in net.routers.values():
        subnets.update(router.subnets)

    graphs = None

    # Create NSDI-style graphs
    if (settings.rules.startswith("nsdi")):
        # Create RAGs
        rags = {} 
        for t in subnets:
            rag = nsdi.RAG(net, l2, t)
            rag.taint()
            rag.render(os.path.join(settings.render_path, ('rag_%s.png' % t)))
            rags[t] = rag

        if (settings.rules == "nsdi"):
            # Create RPGs
            rpgs = {}
            for t in subnets:
                for s in subnets:
                    if (s == t):
                        continue
                    pair = (t, s)
                    rpg = nsdi.RPG(net, pair, rags[t])
                    rpg.render(os.path.join(settings.render_path, 
                        ('rpg_%s-%s.png') % pair))
                    rpgs[pair] = rpg

            graphs = rpgs
        else:
            # Create TPGs
            tpgs = {}
            for t in subnets:
                for s in subnets:
                    if (s == t):
                        continue
                    pair = (t, s)
                    if (settings.rules == "nsdimod"):
                        tpg = nsdi.TPGMod(net, pair, rags[t])
                    else:
                        tpg = nsdi.TPG(net, pair, rags[t])
                    tpg.render(os.path.join(settings.render_path, 
                        ('tpg_%s-%s.png') % pair))
                    tpgs[pair] = tpg

            graphs = tpgs


    # Create pre-NSDI-style graphs
    elif (settings.rules.startswith("prensdi")):
        # Create RPGs
        rpgs = {}
        for t in subnets:
            for s in subnets:
                if (s == t):
                    continue
                pair = (t, s)
                if (settings.rules == "prensdimod"):
                    rpg = prensdi.RPGMod(net, l2, pair)
                else:
                    rpg = prensdi.RPG(net, l2, pair)
                rpg.taint()
                rpg.render(os.path.join(settings.render_path, 
                    ('rpg_%s-%s.png') % pair))
                rpgs[pair] = rpg

        # Create RPGs
        tpgs = {}
        for pair,rpg in rpgs.items():
            if (settings.rules == "prensdimod"):
                tpg = prensdi.TPGMod(net, rpg, pair)
            else:
                tpg = prensdi.TPG(net, rpg, pair)
            tpg.render(os.path.join(settings.render_path, 
                ('tpg_%s-%s.png') % pair))
            tpgs[pair] = tpg

        graphs = tpgs

    if settings.paths and graphs is not None:
        check_paths(net, graphs, settings.verbose)

    if settings.contract and graphs is not None:
        for tc, g in graphs.items():
            print("TPG %s-%s" % tc)
            g.contract()
            g.render(os.path.join(settings.render_path, 
                        ('tpg-contract_%s-%s.png') % tc))

if __name__ == '__main__':
    main()
