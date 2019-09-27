#!/usr/bin/python3

from argparse import ArgumentParser
import config
import nsdi
import os

def main():
    # Parse arguments
    arg_parser = ArgumentParser(description='Tiramisu prototype')
    arg_parser.add_argument('-json', dest='json_path', action='store',
            required=True, help='Path to network json')
    arg_parser.add_argument('-render', dest='render_path', action='store',
            required=True, help='Path to render graphs')
    arg_parser.add_argument('-nsdi', dest='nsdi', action='store_true',
            help='Render NSDI-style graphs')
    settings = arg_parser.parse_args()
    print("Settings: %s" % settings)

    net = config.Network.load(settings.json_path)
    print(net)

    # Generate physical topology
    phy = nsdi.Physical(net)
    phy.render(os.path.join(settings.render_path, 'physical.png'))

    # Determine subnets
    subnets = set()
    for router in net.routers.values():
        subnets.update(router.subnets)

    # Create NSDI-style graphs
    if (settings.nsdi):
        # Create RAGs
        rags = {} 
        for subnet in subnets:
            rag = nsdi.RAG(net, subnet)
            rag.taint()
            rag.render(os.path.join(settings.render_path, 
                    ('rag_%s.png' % subnet)))
            rags[subnet] = rag
        rpg = nsdi.RPG(net)
        rpg.render(os.path.join(settings.render_path, 'rpg.png'))

if __name__ == '__main__':
    main()
