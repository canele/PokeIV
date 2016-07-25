import json
import time

class PokemonData(dict):
    #A dictionary for all of the key information used in pokeIV
    def __init__(self, pokedex, family, cost, config, api):
        self["family"] = family
        self["cost"] = cost
        self["pokedex"] = pokedex
        self["api"] = api
        items = self.parse_inventory(self.get_inventory())
        self.init_all(items["candy"], pokedex, family, cost, config, api, items["pokemon"])
        
    def update_inventory(self):
        items = self.parse_inventory(self.get_inventory())
        self.init_all(items["candy"], pokedex, family, cost, config, api, items["pokemon"])
        
    #takes a list of pokemon from the API, 
    #a candies dict from the API,
    #a pokedex dict {number,name}, 
    #a family dict {number, family}, 
    #an evolve cost dict {number, cost},
    #and the configuration options
    def init_all(self, candies, pokedex, family, cost, config, api=None, pokemon=None):
        self["candy"] = candies
        self["pokedex"] = pokedex
        self["family"] = family
        self["cost"] = cost
        self["config"] = config
        if pokemon is not None:
            self["all"] = sorted(pokemon, key=lambda x: x.iv, reverse=True)
        if api is not None:
            self["api"] = api
        if self["config"]["hard_minimum"]:
            self.set_top()
        else:
            self.set_best()
        self.set_evolve_counts()
        self.set_unique_counts()
        self.set_needed_counts()
        self["extra"] = sorted(list(set(self["all"]) - set(self["best"])), key=lambda x: x.iv)
        self.set_transfer()
        self["other"] = sorted(list(set(self["extra"]) - set(self["transfer"])), key=lambda x: x.iv, reverse=True)
        self.set_evolve()
        
    
    def get_inventory(self):
        # execute the RPC call to get all pokemon and their stats
        self["api"].get_inventory()
        inventory = self["api"].call()
        return inventory
    
    def find_node(self, key, dictionary):
        for k, v in dictionary.items():
            if k == key:
                yield v
            elif isinstance(v, dict):
                for result in self.find_node(key, v):
                    yield result
            elif isinstance(v, list):
                for d in v:
                    for result in self.find_node(key, d):
                        yield result
    
    def parse_inventory(self, inventory):
        pokemon = []
        candy = []
        
        def _add_pokemon(node):
            pok = type('',(),{})
            pok.id = node["id"]
            pok.name = self["pokedex"][str(node["pokemon_id"])]
            pok.family = self["family"][str(node["pokemon_id"])]
            pok.number = node["pokemon_id"]
            pok.stamina = node["individual_stamina"] if "individual_stamina" in node else 0
            pok.attack = node["individual_attack"] if "individual_attack" in node else 0
            pok.defense = node["individual_defense"] if "individual_defense" in node else 0
            pok.iv = ((pok.stamina + pok.attack + pok.defense) / float(45))*100
            pok.ivPercent = pok.iv/100
            pok.cp = node["cp"]
            if int(self["cost"][str(pok.number)]) > 0:
                pok.cost = int(self["cost"][str(pok.number)])
            pokemon.append(pok)
        
        def _add_candy(node):
            if "candy" in node:
                candy.append((str(node["family_id"]),node["candy"]))
            else:
                candy.append((str(node["family_id"]),0))
        
        for node in self.find_node("pokemon_data", inventory):
            if 'is_egg' not in node:
                _add_pokemon(node)
        for node in self.find_node("pokemon_family", inventory):
            _add_candy(node)
            
        candy = dict(candy)
        for p in pokemon:
            p.candy = candy[str(p.family)]
        
        return {"pokemon":pokemon, "candy":candy}

    def set_best(self):
        self["best"] = []

        for p in self["all"]:
            #if there isn't a pokemon in best with the same number (name) as this one, add it
            if not any(x.number == p.number for x in self["best"]):
                self["best"].append(p)
            #if it passes the minimum iv test
            elif p.iv >= float(self["config"]["minimumIV"]):
                self["best"].append(p)
            #if cp_override is set, check CP
            elif self["config"]["cp_override"] is not None and int(self["config"]["cp_override"]) > 0 and int(p.cp) >= int(self["config"]["cp_override"]):
                self["best"].append(p)

        self["best"].sort(key=lambda x: x.iv, reverse=True)
		
    def set_transfer(self):
        self["transfer"] = []
        if self["extra"]:
            used = dict()
            for p in self["extra"]:
                if self.black_listed(p) or not self.white_listed(p):
                    continue
                id = str(p.number)
                used[id] = 0 if id not in used else used[id]
                if self["config"]["force"] or id not in self["evolve_counts"] or used[id] < (self["unique_counts"][id] - self["evolve_counts"][id]):
                    self["transfer"].append(p)
                used[id] = used[id] + 1

        self["transfer"].sort(key=lambda x: x.iv)

    def set_evolve(self):
        self["evolve"] = []
        if any(self["evolve_counts"]):
            count = dict()
            for p in self["all"]:
                if self.black_listed(p) or not self.white_listed(p):
                    continue
                id = str(p.number)
                count[id] = 0 if id not in count else count[id]
                if id in self["evolve_counts"] and count[id] < int(self["evolve_counts"][id]):
                    self["evolve"].append(p)
                    count[id] = count[id] + 1
        self["evolve"].sort(key=lambda x: x.iv, reverse=True)
        
    def set_unique_counts(self):
        self["unique_counts"] = dict()
        for p in self["all"]:
            if (str(p.number) == str(p.family)):
                if str(p.number) in self["unique_counts"]:
                    self["unique_counts"][str(p.number)] = self["unique_counts"][str(p.number)] + 1
                else:
                    self["unique_counts"][str(p.number)] = 1

    #returns true if pokemon is black listed, false otherwise
    def black_listed(self,pokemon):
        if self["config"]["black_list"] is not None and (str(pokemon.number) in self["config"]["black_list"] or pokemon.name.lower() in self["config"]["black_list"]):
            return True
        else:
            return False
            
    #returns true if pokemon is white listed or if white list does not exist, false otherwse
    def white_listed(self,pokemon):
        if self["config"]["white_list"] is None or str(pokemon.number) in self["config"]["white_list"] or pokemon.name.lower() in self["config"]["white_list"]:
            return True
        else:
            return False
            
    def set_evolve_counts(self):
        self["evolve_counts"] = dict()
        total = 0

        for p in self["all"]:
            if self.black_listed(p) or not self.white_listed(p):
                continue
            if str(p.number) == str(p.family) and str(p.number) not in self["evolve_counts"] and hasattr(p,'cost'):
                if int(p.candy/p.cost) > 0:
                    self["evolve_counts"][str(p.number)] = int(p.candy/p.cost)
                    total += int(p.candy/p.cost)
        self["evolve_counts"]["total"] = total

    def set_needed_counts(self):
        self["needed_counts"] = dict()
        for p in self["all"]:
            if str(p.number) in self["evolve_counts"] and str(p.number) in self["unique_counts"]:
                self["needed_counts"][str(p.number)] = self["evolve_counts"][str(p.number)] - self["unique_counts"][str(p.number)]

    def set_top(self):
        self["best"] = []

        for p in self["all"]:
            #if it passes the minimum iv test
            if p.iv >= float(self["config"]["minimumIV"]):			
                self["best"].append(p)

        self["best"].sort(key=lambda x: x.iv, reverse=True)
    
    def get_pokemon_from_id(self, id):
        for p in self["all"]:
            if int(p.id) == int(id):
                return p
        return None
    
    def transfer_pokemon(self, pokemon):
        if isinstance(pokemon, str) or isinstance(pokemon, int):
            self["api"].release_pokemon(pokemon_id=pokemon)
        else:
            self["api"].release_pokemon(pokemon_id=pokemon.id)
        self["api"].call()
        self.update()

    def evolve_pokemon(self, pokemon):
        if isinstance(pokemon, str) or isinstance(pokemon, int):
            self["api"].evolve_pokemon(pokemon_id=pokemon)
        else:
            self["api"].evolve_pokemon(pokemon_id=pokemon.id)
        self["api"].call()
        self.update()
        
    def login(self, config):
        self["config"] = config
        # login
        if not self["api"].login(self["config"]["auth_service"], self["config"]["username"], self["config"]["password"]):
            print("error logging in...")
        self.update()
        
    def update(self):
        items = self.parse_inventory(self.get_inventory())
        self.init_all(items["candy"],self["pokedex"],self["family"], self["cost"], self["config"], self["api"], items["pokemon"])
    
    def reconfigure(self, config, api=None):
        self.init_all(self["candy"],self["pokedex"],self["family"], self["cost"],config, api)