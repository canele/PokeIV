#!/usr/bin/env python

from tkinter import ttk
import tkinter as tk

class PokeIVWindow(tk.Frame):
    def __init__(self, config, data, api, master=None):
        tk.Frame.__init__(self,master)
        self.data = data
        self.api = api
        self.logText = tk.StringVar()
        self.logText.set("idle...")
        self.transfer_ids = []
        self.evolve_ids = []
        self.check_boxes = {}
        self.config = config
        self.config_boxes = {}
        self.create_widgets()
        master.bind("<Escape>", self.key_press)
        self.pack()
        
    def key_press(self, event):
        self.clear_trees()
        
    def best_select(self, event):
        self.clear_trees(self.best_window.tree)
        
    def transfer_select(self, event):
        self.clear_trees(self.transfer_window.tree)
    
    def evolve_select(self, event):
        self.clear_trees(self.evolve_window.tree)
    
    def create_config_window(self):
        self.config_window = tk.Toplevel(self)
        self.config_window.wm_title("Config Window")
        
        for key in list(self.config.keys()):
            if (type(self.config[key]) != type(True)): #if not boolean
                if key == "evolve_list": #deprecated, don't show
                    continue
                self.config_boxes[key] = tk.StringVar()
                if isinstance(self.config[key], list):
                    self.config_boxes[key].set(",".join(map(str,self.config[key])))
                elif self.config[key] is not None:
                    self.config_boxes[key].set(self.config[key])
                else:
                    self.config_boxes[key].set("")
                frame = tk.Frame(self.config_window)
                label = tk.Label(frame, text=key, width=13, anchor="w", justify="left")
                label.pack(side="left")
                entry = tk.Entry(frame, width=50, textvariable=self.config_boxes[key])
                entry.pack(side="right", fill="both", expand=True)
                frame.pack(side="top", fill="both")
        
        save_button = tk.Button(self.config_window, text="Save", command=self.save_config_window)
        save_button.pack(side="bottom", fill="both")
        
    def save_config_window(self):
        self.set_config()
        self.config_window.destroy
        
    def show_config_window(self):
        self.create_config_window()
        return
        
    def hide_config_window(self):
        self.config_window.withdraw()
        return
        
    def reset_windows(self):
        #self.list_windows.pack_forget()
        #self.list_windows = self.create_list_windows(self.master_frame)
        #self.list_windows.pack(side="left", fill="both")
        
        self.reset_tree_window(self.best_window.tree, self.data["best"])
        self.reset_tree_window_other(self.other_window.tree)
        self.reset_tree_window(self.transfer_window.tree, self.data["transfer"])
        self.reset_tree_window(self.evolve_window.tree, self.data["evolve"])
        

    def create_widgets(self):
        self.master_frame = tk.Frame(self)        
        
        topFrame = tk.Frame(self.master_frame)
        self.config_button = tk.Button(topFrame, text="Config", command=self.show_config_window)
        self.refresh_button = tk.Button(topFrame, text="Refresh", command=self.refresh, width=4)
        self.config_button.pack(side="left", fill="both", expand=True)
        self.refresh_button.pack(side="right", fill="both")
        topFrame.pack(side="top", fill="both")
        
        self.list_windows = self.create_list_windows(self.master_frame)
        self.list_windows.pack(side="top", fill="both")
        self.log = tk.Label(self.master_frame, textvariable=self.logText, bg="#D0F0C0", anchor="w", justify="left")
        self.log.pack(side="bottom", fill="both")
        self.init_windows = self.create_interactive(self.master_frame)
        self.init_windows.pack(side="bottom", fill="both")
        self.master_frame.pack(fill="both")
    
    def set_config(self):
        for key in list(self.config_boxes.keys()):
            if self.config_boxes[key].get() == 1:
                self.config[key] = True
            elif self.config_boxes[key].get() == 0:
                self.config[key] = False
            elif (key == "black_list" or key == "white_list") and self.config_boxes[key].get():
                self.config[key] = self.config_boxes[key].get().split(',')
            elif not self.config_boxes[key].get():
                self.config[key] = None
            elif type(self.config_boxes[key].get()) == str:
                self.config[key] = self.config_boxes[key].get()
        
        self.data.reconfigure(self.config)
        self.reset_windows()
    
    def create_checkbuttons(self, master):
        checkboxes = tk.Frame(master)
        
        for key in list(self.config.keys()):
            if (type(self.config[key]) == type(True)): #if boolean
                self.config_boxes[key] = tk.BooleanVar()
                if self.config[key]:
                    self.config_boxes[key].set(1)
                else:
                    self.config_boxes[key].set(0)
                self.check_boxes[key] = tk.Checkbutton(checkboxes, text=key, variable=self.config_boxes[key], command=self.set_config)
                self.check_boxes[key].pack(side="bottom", anchor="w")
                
        return checkboxes
    
    def create_interactive(self, master):
        right_windows = tk.Frame(master)
        
        button_frame = tk.Frame(master)
        action_buttons = tk.Frame(button_frame)
        self.evolve_button = tk.Button(action_buttons, text="Evolve", command=self.evolve_all_pokemon)
        self.evolve_button.pack(side="top", fill="both")
        self.transfer_button = tk.Button(action_buttons, text="Transfer", command=self.transfer_all_pokemon)
        self.transfer_button.pack(side="bottom", fill="both")
        action_buttons.pack(side="left", fill="both", expand=True)
        self.cancel_button = tk.Button(button_frame, text="Cancel", command=self.cancel_actions, width=4, bg="#CD5C5C")
        self.cancel_button.pack(side="right", fill="y")
        button_frame.pack(side="bottom", fill="both")
        
        
        self.tickboxes = self.create_checkbuttons(master)
        self.tickboxes.pack(side="bottom", fill="both")
        
        return right_windows
    
    def create_list_windows(self, master):
        list_windows = tk.Frame(master)
        top_windows = tk.Frame(list_windows)
        btm_windows = tk.Frame(list_windows)
        
        self.best_window = self.create_window('Highest IV Pokemon', self.data["best"], top_windows)
        self.best_window.pack(side="left", fill="both")
        self.best_window.tree.bind('<Button-1>', self.best_select)
        self.best_window.tree.config(selectmode="browse")
        self.other_window = self.create_evolve_count_window('Available evolutions ['+str(self.data["evolve_counts"]["total"])+' / '+str(self.config["max_evolutions"])+']', top_windows)
        self.other_window.pack(side="right", fill="both", expand=True)
        self.other_window.tree.config(selectmode="none")
        self.transfer_window = self.create_window('Transfer candidates', self.data["transfer"], btm_windows)
        self.transfer_window.pack(side="left", fill="both")
        self.transfer_window.tree.bind('<Button-1>', self.transfer_select)
        self.transfer_window.tree.config(selectmode="browse")
        self.evolve_window = self.create_window('Evolution candidates', self.data["evolve"], btm_windows)
        self.evolve_window.pack(side="right", fill="both")
        self.evolve_window.tree.bind('<Button-1>', self.evolve_select)
        self.evolve_window.tree.config(selectmode="browse")
    
        top_windows.pack(side="top", fill="both")
        btm_windows.pack(side="bottom", fill="both")
        
        return list_windows
    
    def create_window(self, name, pokemon, master):
        frame = tk.Frame(master)
        title = tk.Label(frame, text=name)
        title.pack(side="top", fill="both")
        
        cols = self.get_columns()
        tree = ttk.Treeview(frame, columns=list(cols["verbose"][1:]) + ["id"])
        for i, x in enumerate(cols["verbose"]):
            col = '#'+str(i)
            tree.heading(col, text=x, command=lambda i=i: self.sort_tree_column(tree, i, False))
            tree.column(col, width=cols["width"][i], stretch="yes")
        for p in pokemon:
            info = self.get_info(p)
            tree.insert('', 'end', text=info[0], values=list(info[1:]) + [p.id])
        if self.config["verbose"]:
            tree.config(displaycolumns=list(cols["verbose"][1:]))
        else:
            tree.config(displaycolumns=list(cols["min"][1:]))    
        tree.pack(side="left", fill="both")
        
        scroll = tk.Scrollbar(frame)
        scroll.pack(side="right", fill="both")
        
        scroll.config(command=tree.yview)
        tree.config(yscrollcommand=scroll.set)
        
        frame.tree = tree
        frame.scroll = scroll
        frame.title = title
        return frame
        
    def reset_tree_window(self, tree, pokemon):
        for i in tree.get_children():
            tree.delete(i)
            
        for p in pokemon:
            info = self.get_info(p)
            tree.insert('', 'end', text=info[0], values=list(info[1:]) + [p.id])
        
        cols = self.get_columns()
        if self.config["verbose"]:
            tree.config(displaycolumns=list(cols["verbose"][1:]))
        else:
            tree.config(displaycolumns=list(cols["min"][1:]))

    def reset_tree_window_other(self, tree):
        for i in tree.get_children():
            tree.delete(i)
            
        for id in list(self.data["evolve_counts"].keys()):
            if id in self.data["needed_counts"] and id in self.data["unique_counts"] and id in self.data["evolve_counts"]:
                info = (self.data["pokedex"][id],self.data["evolve_counts"][id],self.data["unique_counts"][id],self.data["needed_counts"][id])
                if self.data["needed_counts"][id] <= 0:
                    tree.insert('','end',text=info[0], values=info[1:-1])
                else:
                    tree.insert('','end',text=info[0], values=info[1:])
        
    
    def create_evolve_count_window(self, name, master):
        frame = tk.Frame(master)
        title = tk.Label(frame, text=name)
        title.pack(side="top", fill="both")
        
        cols = {'text': ('POKEMON','EVOLUTIONS','COUNT','NEEDED'),
                'width': (100, 30, 30, 30)}
        tree = ttk.Treeview(frame, columns=cols["text"][1:])
        for i, x in enumerate(cols["text"]):
            col = '#'+str(i)
            tree.heading(col, text=x, command=lambda i=i: self.sort_tree_column(tree, i, False))
            tree.column(col, width=cols["width"][i], stretch="yes")
        for id in list(self.data["evolve_counts"].keys()):
            if id in self.data["needed_counts"] and id in self.data["unique_counts"] and id in self.data["evolve_counts"]:
                info = (self.data["pokedex"][id],self.data["evolve_counts"][id],self.data["unique_counts"][id],self.data["needed_counts"][id])
                if self.data["needed_counts"][id] <= 0:
                    tree.insert('','end',text=info[0], values=info[1:-1])
                else:
                    tree.insert('','end',text=info[0], values=info[1:])
        
        tree.pack(side="left", fill="both", expand=True)
        
        scroll = tk.Scrollbar(frame)
        scroll.pack(side="right", fill="both")
        
        scroll.config(command=tree.yview)
        tree.config(yscrollcommand=scroll.set)
        
        frame.tree = tree
        frame.scroll = scroll
        frame.title = title
        return frame
        
    def sort_tree_column(self, tree, col, reverse):
        l = []
        if col == 0:
            l = [(tree.item(k, "text"), k) for k in tree.get_children('')]
        else:
            l = [(tree.set(k, "#"+str(col)), k) for k in tree.get_children('')]
        
        try:
            l.sort(key=lambda t: int(t[0]), reverse=reverse)
        except ValueError:
            l.sort(reverse=reverse)
            
        for i, (val, k) in enumerate(l):
            tree.move(k, '', i)
            
        tree.heading("#"+str(col), command=lambda: self.sort_tree_column(tree, col, not reverse))
    
    def clear_trees(self, save=None):
        if save != self.best_window.tree:
            for sel in self.best_window.tree.selection():
                self.best_window.tree.selection_remove(sel)
        if save != self.other_window.tree:
            for sel in self.other_window.tree.selection():
                self.other_window.tree.selection_remove(sel)
        if save != self.transfer_window.tree:
            for sel in self.transfer_window.tree.selection():
                self.transfer_window.tree.selection_remove(sel)
        if save != self.evolve_window.tree:
            for sel in self.evolve_window.tree.selection():
                self.evolve_window.tree.selection_remove(sel)
        
    def get_info(self,pokemon):
        return (str(pokemon.name),str(pokemon.attack),str(pokemon.defense),str(pokemon.stamina),str(pokemon.cp),str('{0:>2.2%}').format(pokemon.ivPercent))
        
    def get_columns(self):
        return {'verbose': ('POKEMON','ATK','DEF','STA','CP','IV'),
                'min': ('POKEMON','CP','IV'),
                'width': (100,30,30,30,60,60)}
                    
    def log_info(self, text, level=None):
        self.logText.set(text)
        if level == "working":
            self.log.configure(bg="yellow")
        elif level == "error":
            self.log.configure(bg="red")
        else:
            self.log.configure(bg="#D0F0C0")
    
    def pokemon_selected_action(self, action):
        if action == "evolve" and self.evolve_window.tree.selection():
            id = self.evolve_window.tree.item(self.evolve_window.tree.selection()[0], "values")[-1]
            pokemon = self.data.get_pokemon_from_id(id)
            self.evolve_pokemon(pokemon, False)
            return True
        elif action == "transfer":
            if self.best_window.tree.selection():
                id = self.best_window.tree.item(self.best_window.tree.selection()[0], "values")[-1]
                pokemon = self.data.get_pokemon_from_id(id)
                self.transfer_pokemon(pokemon, False)
                return True
            elif self.transfer_window.tree.selection():
                id = self.transfer_window.tree.item(self.transfer_window.tree.selection()[0], "values")[-1]
                pokemon = self.data.get_pokemon_from_id(id)
                self.transfer_pokemon(pokemon, False)
                return True
            elif self.evolve_window.tree.selection():
                id = self.evolve_window.tree.item(self.evolve_window.tree.selection()[0], "values")[-1]
                pokemon = self.data.get_pokemon_from_id(id)
                self.transfer_pokemon(pokemon, False)
                return True
        return False
    
    def evolve_pokemon(self, pokemon, cont):
        self.log_info('{0:<35} {1:<8} {2:<8.2%}'.format('evolving pokemon: '+str(pokemon.name),str(pokemon.cp),pokemon.ivPercent), "working")
        self.disable_buttons()
        self.evolve_ids.append(self.evolve_button.after(int(self.config["evolution_delay"])*1000, lambda: self.evolve(pokemon, cont)))
        
    def transfer_pokemon(self, pokemon, cont):
        self.log_info('{0:<35} {1:<8} {2:<8.2%}'.format('transferring pokemon: '+str(pokemon.name),str(pokemon.cp),pokemon.ivPercent,), "working")
        self.disable_buttons()
        self.transfer_ids.append(self.transfer_button.after(int(self.config["transfer_delay"])*1000, lambda: self.transfer(pokemon, cont)))
    
    def evolve_all_pokemon(self):
        #if there was a pokemon selected from evolve list, evolve only that
        if self.pokemon_selected_action("evolve"):
            return
        
        if self.data["evolve"]:
            p = self.data["evolve"][0]
            self.evolve_pokemon(p, True)
        else:
            self.log_info("idle...")
            self.reset_windows()
        
    def transfer_all_pokemon(self):
        #if there was a pokemon selected from any list, transfer only that
        if self.pokemon_selected_action("transfer"):
            return
        
        if self.data["transfer"]:
            p = self.data["transfer"][0]
            self.transfer_pokemon(p, True)
        else:
            self.log_info("idle...")
            self.reset_windows()
            
    def disable_buttons(self):
        self.transfer_button.config(state="disabled")
        self.evolve_button.config(state="disabled")
        
    def enable_buttons(self):
        self.transfer_button.config(state="normal")
        self.evolve_button.config(state="normal")
        
    def transfer(self, p, cont):
        self.data.transfer_pokemon(p)
        self.enable_buttons()
        if cont and self.data["transfer"]:
            self.transfer_all_pokemon()
        else:
            self.log_info("idle...")
        self.reset_windows()

    def evolve(self, p, cont):
        self.data.evolve_pokemon(p)
        self.enable_buttons()
        if cont and self.data["evolve"]:
            self.evolve_all_pokemon()
        else:
            self.log_info("idle...")
        self.reset_windows()
    
    def cancel_actions(self):
        for id in self.transfer_ids[:]:
            self.transfer_button.after_cancel(id)
            self.transfer_ids.remove(id)
        for id in self.evolve_ids[:]:
            self.evolve_button.after_cancel(id)
            self.evolve_ids.remove(id)
        self.enable_buttons()
        self.log_info("idle...")
        self.reset_windows()
        
    def refresh(self):
        self.data.update()
        self.reset_windows()