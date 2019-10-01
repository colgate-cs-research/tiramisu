#!/usr/bin/python3

from argparse import ArgumentParser
import config
import graph
import nsdi
import os
import prensdi

def main():
    # Parse arguments
    arg_parser = ArgumentParser(description='Tiramisu prototype')
    arg_parser.add_argument('-json', dest='json_path', action='store',
            required=True, help='Path to network json')
    arg_parser.add_argument('-render', dest='render_path', action='store',
            required=True, help='Path to render graphs')
    arg_parser.add_argument('-rules', dest='rules', action='store',
            help='Rules to follow', choices=["nsdi", "prensdi"])
    arg_parser.add_argument('-paths', dest='paths', action='store_true',
            help='Check paths')
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

    # Determine subnets
    subnets = set()
    for router in net.routers.values():
        subnets.update(router.subnets)

    graphs = None

    # Create NSDI-style graphs
    if (settings.rules == "nsdi"):
        # Create RAGs
        rags = {} 
        for t in subnets:
            rag = nsdi.RAG(net, l2, t)
            rag.taint()
            rag.render(os.path.join(settings.render_path, ('rag_%s.png' % t)))
            rags[t] = rag

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

    # Create pre-NSDI-style graphs
    elif (settings.rules == "prensdi"):
        # Create RPGs
        rpgs = {}
        for t in subnets:
            for s in subnets:
                if (s == t):
                    continue
                pair = (t, s)
                rpg = prensdi.RPG(net, l2, pair)
                rpg.taint()
                rpg.render(os.path.join(settings.render_path, 
                    ('rpg_%s-%s.png') % pair))
                rpgs[pair] = rpg

        # Create RPGs
        tpgs = {}
        for pair,rpg in rpgs.items():
            tpg = prensdi.TPG(net, rpg, pair)
            tpg.render(os.path.join(settings.render_path, 
                ('tpg_%s-%s.png') % pair))
            tpgs[pair] = tpg

        graphs = tpgs

    if settings.paths and graphs is not None:
        for p in net.paths:
            g = graphs[(p.origin, p.endpoint)]
            found, hops = g.has_path(p.failset)
            print("%s %s" % (p, found))
            if (found):
                print('\t'+'\n\t'.join(hops))

if __name__ == '__main__':
    main()
