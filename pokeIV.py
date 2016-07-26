#!/usr/bin/env python
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
import tkinter as tk

from collections import OrderedDict
from pokemondata import PokemonData
from pokeivwindow import PokeIVWindow

# add directory of this file to PATH, so that the package will be found
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))

# import Pokemon Go API lib
from pgoapi import pgoapi
from pgoapi import utilities as util

# other stuff
from google.protobuf.internal import encoder
from geopy.geocoders import GoogleV3
from s2sphere import Cell, CellId, LatLng


log = logging.getLogger(__name__)
def setupLogger():
    # log settings
    # log format
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(module)10s] [%(levelname)5s] %(message)s')
    # log level for http request class
    logging.getLogger("requests").setLevel(logging.WARNING)
    # log level for main pgoapi class
    logging.getLogger("pgoapi").setLevel(logging.INFO)
    # log level for internal pgoapi class
    logging.getLogger("rpc_api").setLevel(logging.INFO)

def init_config():
    parser = argparse.ArgumentParser()
    config_file = "config.json"

    # If config file exists, load variables from json
    load   = {}
    if os.path.isfile(config_file):
        with open(config_file) as data:
            load.update(json.load(data))
    
    # Read passed in Arguments
    required = lambda x: not x in load
    parser.add_argument("-a", "--auth_service", help="Auth Service ('ptc' or 'google')",required=required("auth_service"))
    parser.add_argument("-u", "--username", help="Username", required=required("username"))
    parser.add_argument("-p", "--password", help="Password")
    parser.add_argument("-t", "--transfer", help="Transfers all but the highest of each pokemon (see -ivmin)", action="store_true")
    parser.add_argument("-e", "--evolve", help="Evolves as many T1 pokemon that it can (starting with highest IV)", action="store_true")
    parser.add_argument("-m", "--minimumIV", help="All pokemon equal to or above this IV value are kept regardless of duplicates")
    parser.add_argument("-me", "--max_evolutions", help="Maximum number of evolutions in one pass")
    parser.add_argument("-ed", "--evolution_delay", help="delay between evolutions in seconds")
    parser.add_argument("-td", "--transfer_delay", help="delay between transfers in seconds")
    parser.add_argument("-hm", "--hard_minimum", help="transfer candidates will be selected if they are below minimumIV (will transfer unique pokemon)", action="store_true")
    parser.add_argument("-cp", "--cp_override", help="will keep pokemon that have CP equal to or above the given limit, regardless of IV")
    parser.add_argument("-v", "--verbose", help="displays additional information about each pokemon", action="store_true")
    parser.add_argument("-el", "--evolve_list", help="Evolve lsit has been deprecated. Please use white list instead (-wl).", action="append")
    parser.add_argument("-wl", "--white_list", help="list of the only pokemon to transfer and evolve by ID or name (ex: -wl 1 = -wl bulbasaur)", action="append")
    parser.add_argument("-bl", "--black_list", help="list of the pokemon not to transfer and evolve by ID or name (ex: -bl 1 = -bl bulbasaur)", action="append")
    parser.add_argument("-f", "--force", help="forces all pokemon not passing the IV threshold to be transfer candidates regardless of evolution", action="store_true")
    config = parser.parse_args()
    
    # Passed in arguments shoud trump
    for key in config.__dict__:
        if key in load and config.__dict__[key] is None and load[key]:
            if key == "black_list" or key == "white_list":
                config.__dict__[key] = str(load[key]).split(',')
            else:
                config.__dict__[key] = str(load[key])
        elif key in load and (type(config.__dict__[key]) == type(True)) and not config.__dict__[key] and load[key]: #if it's boolean and false
            if str(load[key]) == "True":
                config.__dict__[key] = True
    
    if config.__dict__["password"] is None:
        logging.info("Secure Password Input (if there is no password prompt, use --password <pw>):")
        config.__dict__["password"] = getpass.getpass()

    if config.auth_service not in ['ptc', 'google']:
        logging.error("Invalid Auth service specified! ('ptc' or 'google')")
        return None
        
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
        logging.error("Evolve lsit has been deprecated. Please use white list instead (-wl).")
        return
    
    if config.white_list is not None:
        config.white_list = [x.lower() for x in config.white_list]
    if config.black_list is not None:
        config.black_list = [x.lower() for x in config.black_list]
    
    return OrderedDict(sorted(vars(config).items())) #namespaces are annoying => sorted dict

def print_header(title):
    print('{0:<15} {1:^20} {2:>15}'.format('------------',title,'------------'))

def print_pokemon(pokemon, verbose):
    if verbose:
        print_pokemon_verbose(pokemon)
    else:
        print_pokemon_min(pokemon)
    
def print_pokemon_min(pokemon):
    print('{0:<10} {1:>8} {2:>8}'.format('[pokemon]','[CP]','[IV]'))
    for p in pokemon:
        print('{0:<10} {1:>8} {2:>8.2%}'.format(str(p.name),str(p.cp),p.ivPercent)) 

def print_pokemon_verbose(pokemon):
    print('{0:<10} {1:>6} {2:>6} {3:>6} {4:>8} {5:>8}'.format('[POKEMON]','[ATK]','[DEF]','[STA]','[CP]','[IV]'))
    for p in pokemon:
        print('{0:<10} {1:>6} {2:>6} {3:>6} {4:>8} {5:>8.2%}'.format(str(p.name),str(p.attack),str(p.defense),str(p.stamina),str(p.cp),p.ivPercent))

def print_evolve_candidates(data):
    if data["evolve"]:
        print_header('Available evolutions')
        print_header('TOTAL: '+str(data["evolve_counts"]["total"])+' / '+data["config"]["max_evolutions"])
        print('{0:<10} {1:<15} {2:<17} {3:>10}'.format('[pokemon]','[# evolutions]','[# in inventory]','[# needed]'))
        for id in list(data["evolve_counts"].keys()):
            if id in data["needed_counts"] and id in data["unique_counts"] and data["needed_counts"][id] <= 0:
                print('{0:<10} {1:^15} {2:^17} {3:^10}'.format(data["pokedex"][id],data["evolve_counts"][id],data["unique_counts"][id],""))
            elif id in data["needed_counts"] and id in data["unique_counts"]:
                print('{0:<10} {1:^15} {2:^17} {3:^10}'.format(data["pokedex"][id],data["evolve_counts"][id],data["unique_counts"][id],data["needed_counts"][id]))

def transfer_pokemon(data, session):
    if data["config"]["transfer"] and data["transfer"]:
        print('{0:<15} {1:^20} {2:>15}'.format('------------','Transferring','------------'))
        for p in data["transfer"][:]:
            id = str(p.number)
            print('{0:<35} {1:<8} {2:<8.2%}'.format('transferring pokemon: '+str(p.name),str(p.cp),p.ivPercent))
            data["api"].release_pokemon(pokemon_id=p.id)
            data["api"].call()
            if id in list(data["unique_counts"].keys()):
                data["unique_counts"][id] = data["unique_counts"][id] - 1 #we now have one fewer of these...
            if p in data["transfer"]:
                data["transfer"].remove(p)
            if p in data["all"]:
                data["all"].remove(p)
            time.sleep(int(data["config"]["transfer_delay"]))

def evolve_pokemon(data, session):
    if data["config"]["evolve"] and data["evolve"]:
        for p in data["evolve"][:]:
            id = str(p.number)
            print('{0:<35} {1:<8} {2:<8.2%}'.format('evolving pokemon: '+str(p.name),str(p.cp),p.ivPercent))
            data["api"].evolve_pokemon(pokemon_id=p.id)
            data["api"].call()
            data["evolve_counts"][id] = data["evolve_counts"][id] - 1
            data["unique_counts"][id] = data["unique_counts"][id] - 1
            if p in data["evolve"]:
                data["evolve"].remove(p)
            if p in data["all"]:
                data["all"].remove(p)
            if p in data["extra"]:
                data["extra"].remove(p)
            time.sleep(int(data["config"]["evolution_delay"]))

def main():
    setupLogger()
    log.debug('Logger set up')

    config = init_config()
    if not config:
        return

    # instantiate pgoapi
    api = pgoapi.PGoApi()
    
    # -- dictionaries for pokedex, families, and evolution prices
    with open('names.tsv') as f:
        f.readline()
        pokedex = dict(csv.reader(f, delimiter='\t'))
        
    with open('families.tsv') as f:
        f.readline()
        family = dict(csv.reader(f, delimiter='\t'))    
        
    with open('evolves.tsv') as f:
        f.readline()
        cost = dict(csv.reader(f, delimiter='\t'))
    
    data = PokemonData(pokedex, family, cost, config, api)
    
    if len(data["all"]) == 0:
        print('You have no pokemon...')
        return
    
    #------- best pokemon
    if data["best"]:
        print_header('Highest IV Pokemon')
        print_pokemon(data["best"], data["config"]["verbose"])
    #------- transferable pokemon
    if data["transfer"]:
        print_header('May be transfered')
        print_pokemon(data["transfer"], data["config"]["verbose"])
    #------- extras that aren't to be transfered
    if data["other"]:
        print_header('Other Pokemon')
        print_pokemon(data["other"], data["config"]["verbose"])
    #------- evolve candidate  pokemon
    if data["evolve"]:
        print_evolve_candidates(data)
    #------- transfer extra pokemon
    if data["config"]["transfer"] and data["transfer"]:
        transfer_pokemon(data, session)
    #------- evolving t1 pokemon
    if data["config"]["evolve"] and data["evolve"]:
        evolve_pokemon(data, session)
    
if __name__ == '__main__':
    main()