#!/usr/bin/env python
#This software uses pgoapi - see pgoapi-license.txt

import os
import re
import sys
import json
import time
import struct
import pprint
import logging
import requests
import argparse
import getpass
import csv
import time

from tkinter import ttk
import tkinter as tk

from collections import OrderedDict
from pokemondata import PokemonData
from pokeivwindow import PokeIVWindow

# add directory of this file to PATH, so that the package will be found
try:
    root = os.path.normpath(os.path.dirname(os.path.realpath(__file__)))
except NameError:
    root = os.path.normpath(os.path.dirname(os.path.realpath(sys.argv[0])))
    
sys.path.append(os.path.dirname(root))

# import Pokemon Go API lib
from pgoapi import pgoapi
from pgoapi import utilities as util

# other stuff
from google.protobuf.internal import encoder
from geopy.geocoders import GoogleV3
from s2sphere import Cell, CellId, LatLng


log = logging.getLogger(__name__)
def setupLogger():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s [%(module)10s] [%(levelname)5s] %(message)s')
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("pgoapi").setLevel(logging.INFO)
    logging.getLogger("rpc_api").setLevel(logging.INFO)

def init_config():
    parser = argparse.ArgumentParser()
    config_file = "config.json"

    load   = {}
    if os.path.isfile(config_file):
        with open(config_file) as data:
            load.update(json.load(data))
    
    required = lambda x: not x in load
    parser.add_argument("-a", "--auth_service", help="Auth Service ('ptc' or 'google')")
    parser.add_argument("-u", "--username", help="Username")
    parser.add_argument("-p", "--password", help="Password")
    parser.add_argument("-l", "--location", help="Physical location of your character")
    parser.add_argument("-m", "--minimumIV", help="All pokemon equal to or above this IV value are kept regardless of duplicates")
    parser.add_argument("-me", "--max_evolutions", help="Maximum number of evolutions in one pass")
    parser.add_argument("-ed", "--evolution_delay", help="delay between evolutions in seconds")
    parser.add_argument("-td", "--transfer_delay", help="delay between transfers in seconds")
    parser.add_argument("-rd", "--rename_delay", help="delay between renames in seconds")
    parser.add_argument("-ud", "--upgrade_delay", help="delay between upgrades in seconds")
    parser.add_argument("-hm", "--hard_minimum", help="transfer candidates will be selected if they are below minimumIV (will transfer unique pokemon)", action="store_true")
    parser.add_argument("-cp", "--cp_override", help="will keep pokemon that have CP equal to or above the given limit, regardless of IV")
    parser.add_argument("-v", "--verbose", help="displays additional information about each pokemon", action="store_true")
    parser.add_argument("-el", "--evolve_list", help="Evolve lsit has been deprecated. Please use white list instead (-wl).", action="append")
    parser.add_argument("-wl", "--white_list", help="list of the only pokemon to transfer and evolve by ID or name (ex: -wl 1 = -wl bulbasaur)", action="append")
    parser.add_argument("-bl", "--black_list", help="list of the pokemon not to transfer and evolve by ID or name (ex: -bl 1 = -bl bulbasaur)", action="append")
    parser.add_argument("-f", "--force", help="forces all pokemon not passing the IV threshold to be transfer candidates regardless of evolution", action="store_true")
    parser.add_argument("-rf", "--rename_format", help="The pokemon renaming format. See config comments")
    parser.add_argument("-eq", "--equation", help="Equation to use for IV calculation--see config file for details")
    parser.add_argument("-dn", "--display_nickname", help="Display nicknames instead of pokemon type", action="store_true")
    parser.add_argument("-la", "--language", help="Pokemon names are displayed in the given language. German and English currently supported")
    config = parser.parse_args()
    
    for key in config.__dict__:
        if key in load and config.__dict__[key] is None and load[key]:
            if key == "black_list" or key == "white_list":
                config.__dict__[key] = str(load[key]).split(',')
            else:
                config.__dict__[key] = str(load[key])
        elif key in load and (type(config.__dict__[key]) == type(True)) and not config.__dict__[key] and load[key]: #if it's boolean and false
            if str(load[key]) == "True":
                config.__dict__[key] = True
        
    if config.__dict__["minimumIV"] is None:
        config.__dict__["minimumIV"] = "101"
    if config.__dict__["max_evolutions"] is None:
        config.__dict__["max_evolutions"] = "71"
    if config.__dict__["evolution_delay"] is None:
        config.__dict__["evolution_delay"] = "25"
    if config.__dict__["transfer_delay"] is None:
        config.__dict__["transfer_delay"] = "10"
    
    if config.white_list is not None and config.black_list is not None:
        logging.error("Black list and white list can not be used together.")
        return
    
    if config.evolve_list is not None:
        logging.error("Evolve list has been deprecated. Please use white list instead (-wl).")
        return
    
    if config.white_list is not None:
        config.white_list = [x.lower() for x in config.white_list]
    if config.black_list is not None:
        config.black_list = [x.lower() for x in config.black_list]
    
    return OrderedDict(sorted(vars(config).items()))     

def main():
    setupLogger()
    log.debug('Logger set up')
    
    #-- initialize config
    config = init_config()
    if not config:
        return
        
    if config["password"] is None or config["username"] is None or config["auth_service"] not in ['ptc', 'google'] or config["location"] is None:
        start(config)
    else:
        start(config, login=True)
    
def start(config, login=False):
    # -- dictionaries for pokedex, families, and evolution prices
    with open(os.path.normpath(os.path.join(root, 'pgoapi','pokemon.json'))) as f:
        pokemonInfo = json.load(f)
        
    with open(os.path.normpath(os.path.join(root, 'pgoapi','moves.json'))) as f:
        moveInfo = json.load(f)
        
    with open(os.path.normpath(os.path.join(root, 'pgoapi','types.json'))) as f:
        types = json.load(f)
    
    with open('german-names.tsv') as f:
        f.readline()
        german = dict(csv.reader(f, delimiter='\t'))    
        
    with open('families.tsv') as f:
        f.readline()
        family = dict(csv.reader(f, delimiter='\t'))    
        
    with open('evolves.tsv') as f:
        f.readline()
        cost = dict(csv.reader(f, delimiter='\t'))
        
    pokedex = dict([(int(p["Number"]),p["Name"]) for p in pokemonInfo])
    moves = dict([(int(m["id"]),{"type":m["type"],"name":m["name"]}) for m in moveInfo])
    
    # -- change language if selected -->
    if config["language"] is not None and config["language"].lower() == 'german':
        for k,v in pokedex.items():
            pokedex[k] = german[str(k)];
            
    
    # instantiate pgoapi
    api = pgoapi.PGoApi()
    
    data = PokemonData(pokedex, moves, types, family, cost, config, api, login)
    
    main_window = tk.Tk()
    
    main_window.style = ttk.Style()
    main_window.style.theme_use("classic")
    
    app = PokeIVWindow(config,data,master=main_window)
    app.mainloop()
    
if __name__ == '__main__':
    main()