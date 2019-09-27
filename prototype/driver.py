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
    settings = arg_parser.parse_args()
    print("Settings: %s" % settings)

    net = config.Network.load(settings.json_path)
    print(net)

    phy = nsdi.Physical(net)
    phy.render(os.path.join(settings.render_path, 'physical.png'))
    rag = nsdi.RAG(net)
    rag.render(os.path.join(settings.render_path, 'rag.png'))
    rpg = nsdi.RPG(net)
    rpg.render(os.path.join(settings.render_path, 'rpg.png'))

if __name__ == '__main__':
    main()
