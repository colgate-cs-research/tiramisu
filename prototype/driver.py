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
    arg_parser.add_argument('-nsdi', dest='nsdi', action='store_true',
            help='Render NSDI-style graphs')
    arg_parser.add_argument('-prensdi', dest='prensdi', action='store_true',
            help='Render pre-NSDI-style graphs')
    settings = arg_parser.parse_args()
    print("Settings: %s" % settings)

    net = config.Network.load(settings.json_path)
    print(net)

    # Generate physical and layer 2
    phy = graph.Physical(net)
    phy.render(os.path.join(settings.render_path, 'physical.png'))
    l2 = graph.Layer2(net)
    l2.render(os.path.join(settings.render_path, 'layer2.png'))
    for router in net.routers.values():
        for vlan in router.vlans.values():
            print('%s:\n\t%s' % (vlan, 
                '\n\t'.join([str(v) for v in l2.get_adjacent_vlans(vlan)])))

    # Determine subnets
    subnets = set()
    for router in net.routers.values():
        subnets.update(router.subnets)

    # Create NSDI-style graphs
    if (settings.nsdi):
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

    # Create pre-NSDI-style graphs
    if (settings.prensdi):
        # Create RPGs
        rpgs = {}
        for t in subnets:
            for s in subnets:
                if (s == t):
                    continue
                pair = (t, s)
                rpg = prensdi.RPG(net, pair)
                rpg.taint()
                rpg.render(os.path.join(settings.render_path, 
                    ('rpg_%s-%s.png') % pair))
                rpgs[pair] = rpg

if __name__ == '__main__':
    main()
