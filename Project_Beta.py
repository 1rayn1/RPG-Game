import curses
import random
import time
import json
import os

#Saves the game progress to savegame.json
SAVE_FILE = "savegame.json"

#Defines a class called Monster that defines the stats of monsters
class Monster:
    def __init__(self, name, base_hp, base_attack, base_speed, base_def, level=1, elite=False):
        self.name = name
        self.level = level
        self.hp = base_hp + level * 5
        self.attack = base_attack + level * 2
        self.speed = base_speed + level // 2
        self.defense = base_def + level * 2
        self.elite = elite

class Item:
    def __init__(self,name,damage,dex,crit,mana):
        self.name = name
        self.damage = damage
        self.dex = dex
        self.crit = crit
        self.mana = mana

class Skill:
    def __init__(self, name, description, skill_type, mana_cost=0, stamina_cost = 0, cooldown=0,
                 required_class=None, rank="C", passive=False, level_required=1, custom_name=None, effect = None, duration = 0, power = 1.0):
        self.name = name
        self.custom_name = custom_name or name  # Default to original name if no custom name given
        self.description = description
        self.skill_type = skill_type
        self.mana_cost = mana_cost
        self.stamina_cost = stamina_cost
        self.cooldown = cooldown
        self.required_class = required_class
        self.rank = rank
        self.passive = passive
        self.level_required = level_required
        self.effect = effect
        self.duration = duration
        self.power = power

    def __repr__(self):
        return f"<Skill: {self.custom_name} ({self.rank})>"

# Returns the stats of the chosen monster
def create_monster(name, level_range):
    level = random.randint(level_range[0], level_range[1])
    
    if name == "Slime":
        monster = Monster("Slime", base_hp=10, base_attack=3, base_speed=1, base_def=1, level=level)
    elif name == "Goblin":
        monster = Monster("Goblin", base_hp=30, base_attack=6, base_speed=10, base_def=3, level=level)
    elif name == "Kobold":
        monster = Monster("Kobold", base_hp=35, base_attack=7, base_speed=5, base_def=4, level=level)
    elif name == "Orc":
        monster = Monster("Orc", base_hp=100, base_attack=30, base_speed=2, base_def=6, level=level)
    else:
        monster = Monster(name, base_hp=15, base_attack=5, base_speed=2, base_def=2, level=level)

    if random.random() < 0.0001:
        monster.name = "Elite " + monster.name
        monster.hp *= 2
        monster.attack *= 2
        monster.defense *= 2
        monster.elite = True

    return monster

def rename_skill_menu(stdscr, skills):
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "== Rename Skills ==")
        for i, skill in enumerate(skills):
            stdscr.addstr(i + 1, 0, f"{i + 1}. {skill.custom_name} (original: {skill.name})")

        stdscr.addstr(len(skills) + 2, 0, "Enter number to rename, or 'b' to go back:")
        stdscr.refresh()
        key = stdscr.getch()

        if key == ord('b'):
            break
        elif ord('1') <= key <= ord(str(min(9, len(skills)))):
            index = key - ord('1')
            stdscr.clear()
            stdscr.addstr(0, 0, f"Renaming skill: {skills[index].custom_name}")
            stdscr.addstr(1, 0, "Enter new name (max 20 chars): ")
            curses.echo()
            new_name = stdscr.getstr(2, 0, 20).decode("utf-8")
            curses.noecho()

            if new_name:
                skills[index].custom_name = new_name

#Determines how much xp is given once a monster is defeated
#Also determines whether someone levels up and how rewards are distributed.
def gain_xp(stats, amount):
    stats["xp"] += amount
    leveled_up = False
    while stats["xp"] >= stats["level"] * 10:
        stats["xp"] -= stats["level"] * 10
        stats["level"] += 1
        stats["skill_points"] += 5
        stats["current_mana"] = stats["mana"]  # Full restore
        leveled_up = True
    return leveled_up

def new_game():
    stats = {
        "hp": 20, 
        "attack": 5, 
        "defense": 1, 
        "speed": 2,
        "mana": 10,  # Max mana
        "current_mana": 10,  # Current mana (changes in battle)
        "skill_points": 0, 
        "xp": 0, 
        "level": 1, 
        "gold": 1,
        "wielded_index": None,
        "class_path": None,
    }
    inventory = []
    starter_sword = Item("Rusty Sword", damage=3, dex=0, crit=1, mana=0)
    inventory.append(starter_sword)

    # Starting coordinates
    player_x, player_y = 0, 0

    return stats, inventory, player_x, player_y




#Saves the game to savegame.json
def save_game(stats, player_x, player_y):
    data = {
        "stats": stats,
        "player_x": player_x,
        "player_y": player_y,
        "quests": {
            str(pos): {
                "progress": npc.get("quest", {}).get("progress", 0),
                "completed": npc.get("quest", {}).get("completed", False),
                "reward_given": npc.get("quest", {}).get("reward_given", False)
            } for pos, npc in npcs.items() if "quest" in npc
        }
    }
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)

#Once saved, this function allows the user to restart their progress(if they saved it)
def load_game():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
        stats, player_x, player_y = data["stats"], data["player_x"], data["player_y"]

        # Fallback for older saves: ensure 'class_path' exists
        if "class_path" not in stats:
            stats["class_path"] = None

        for pos_str, quest_data in data.get("quests", {}).items():
            pos = eval(pos_str)
            if pos in npcs and "quest" in npcs[pos]:
                npcs[pos]["quest"]["progress"] = quest_data.get("progress", 0)
                npcs[pos]["quest"]["completed"] = quest_data.get("completed", False)
                npcs[pos]["reward_given"] = quest_data.get("reward_given", False)
        return stats, player_x, player_y
    return None

#This is how the user fights moonsters
def battle(stdscr, monster_name, stats, inventory, skills, level_range=(1, 1)):
    # --- One-turn empower state ---
    empowered_mult = 1.0
    empowered_turns = 0  # when >0, apply on next 'attack' and then reset

    monster = create_monster(monster_name, level_range)
    player_hp = stats["hp"]
    monster_hp = monster.hp
    weapon_damage = inventory[stats["wielded_index"]].damage if stats.get("wielded_index") is not None else 0

    # cooldowns tracked by skill.name
    skill_cooldowns = {skill.name: 0 for skill in skills}
    last_action = "attack"  # default action

    while player_hp > 0 and monster_hp > 0:
        stdscr.clear()
        stdscr.addstr(0, 0, f"{monster.name} (Lv {monster.level}) HP: {monster_hp}")
        stdscr.addstr(1, 0, f"Your HP: {player_hp}, MP: {stats['current_mana']}/{stats['mana']}")
        stdscr.addstr(3, 0, "1-9 to choose a skill, 'a' to attack, Enter to repeat last action.")
        stdscr.refresh()

        stdscr.timeout(1000)  # 1 second to change action, else continue with last_action
        key = stdscr.getch()
        stdscr.timeout(-1)

        # --- Skill selection ---
        if ord('1') <= key <= ord(str(min(9, len(skills)))):
            idx = key - ord('1')
            last_action = skills[idx].name
        elif key == ord('a'):
            last_action = "attack"
        # else: keep last_action

        # --- Resolve Player action ---
        if last_action == "attack":
            # include monster.defense so debuffs matter
            base = stats["attack"] + weapon_damage - monster.defense
            dmg = max(int(base * (empowered_mult if empowered_turns > 0 else 1.0)), 1)
            monster_hp -= dmg
            if empowered_turns > 0:
                stdscr.addstr(5, 0, f"Empowered strike! You attack for {dmg} damage!")
                empowered_turns = 0
                empowered_mult = 1.0
            else:
                stdscr.addstr(5, 0, f"You attack for {dmg} damage!")

        else:
            # Using a skill by name
            skill_obj = next((sk for sk in skills if sk.name == last_action), None)

            if not skill_obj:
                # safety fallback
                base = stats["attack"] + weapon_damage - monster.defense
                dmg = max(int(base), 1)
                monster_hp -= dmg
                stdscr.addstr(5, 0, f"(Unknown skill) You attack for {dmg} damage.")
                last_action = "attack"
            else:
                # Check requirements BEFORE applying effects
                can_use = (
                    stats["level"] >= skill_obj.level_required
                    and stats["current_mana"] >= skill_obj.mana_cost
                    and skill_cooldowns.get(skill_obj.name, 0) == 0
                )

                if not can_use:
                    # fallback basic attack if skill not available
                    base = stats["attack"] + weapon_damage - monster.defense
                    dmg = max(int(base), 1)
                    monster_hp -= dmg
                    stdscr.addstr(5, 0, f"{skill_obj.custom_name} unavailable, you attack for {dmg} damage!")
                    last_action = "attack"
                else:
                    # pay costs & set cooldowns
                    stats["current_mana"] -= skill_obj.mana_cost
                    skill_cooldowns[skill_obj.name] = skill_obj.cooldown

                    # --- Handle effects ---
                    if skill_obj.effect == "damage_buff":
                        # buff the NEXT attack only
                        empowered_mult = float(skill_obj.power or 1.8)
                        empowered_turns = 1
                        stdscr.addstr(5, 0, "Your entire body glows with power! Your next attack will be stronger.")
                        last_action = "attack"  # default next action to attack so it flows

                    elif skill_obj.effect == "mons_defense_debuff":
                        # If power < 1.0, treat as multiplicative; else treat as flat reduction
                        p = skill_obj.power
                        if p is None:
                            p = 0.9
                        if p < 1.0:
                            monster.defense = max(0, int(monster.defense * p))
                            stdscr.addstr(5, 0, "You weaken the foe's guard! Their defense drops.")
                        else:
                            monster.defense = max(0, monster.defense - int(p))
                            stdscr.addstr(5, 0, "You pierce their armor! Their defense drops.")
                        last_action = "attack"

                    elif skill_obj.effect == "hp_buff":
                        # simple heal based on level or power
                        heal = int(stats["level"] * 2) if skill_obj.power in (None, 0) else int(skill_obj.power)
                        player_hp += heal
                        stdscr.addstr(5, 0, f"You bless yourself and heal {heal} HP.")
                        last_action = "attack"

                    else:
                        # Example direct-damage skills by name (Fireball, Arcane Bolt), if present
                        if skill_obj.name == "Fireball":
                            base = stats["attack"] + 5 - monster.defense
                            dmg = max(int(base), 1)
                            monster_hp -= dmg
                            stdscr.addstr(5, 0, f"You cast Fireball for {dmg} damage!")
                        elif skill_obj.name == "Arcane Bolt":
                            base = stats["attack"] + 3 - monster.defense
                            dmg = max(int(base), 1)
                            monster_hp -= dmg
                            stdscr.addstr(5, 0, f"You fire an Arcane Bolt for {dmg} damage!")
                        else:
                            # generic active: small hit
                            base = stats["attack"] + 2 - monster.defense
                            dmg = max(int(base), 1)
                            monster_hp -= dmg
                            stdscr.addstr(5, 0, f"You use {skill_obj.custom_name} for {dmg} damage!")
                        # keep last_action as the skill you just used; Enter will repeat unless player presses 'a'
                        # If you prefer to revert to attack next turn, uncomment:
                        last_action = "attack"

        # --- Monster action ---
        if monster_hp > 0:
            incoming = max(monster.attack - stats["defense"], 1)
            player_hp -= incoming
            stdscr.addstr(7, 0, f"{monster.name} hits you for {incoming} damage!")

        # --- Cooldowns tick ---
        for name in skill_cooldowns:
            if skill_cooldowns[name] > 0:
                skill_cooldowns[name] -= 1

        # --- Mana regen (1 per second) ---
        if stats["current_mana"] < stats["mana"]:
            stats["current_mana"] = min(stats["mana"], stats["current_mana"] + 1)

        stdscr.refresh()
        time.sleep(1)

    # --- Battle result ---
    stdscr.clear()
    if player_hp > 0:
        base_xp = {"Slime": 5, "Goblin": 10, "Kobold": 15, "Orc": 40}.get(monster.name.replace("Elite ", ""), 5)
        xp_gain = base_xp + (monster.level * 2)
        if monster.elite:
            xp_gain *= 2

        leveled_up = gain_xp(stats, xp_gain)
        stdscr.addstr(0, 0, f"You defeated the {monster.name}! You gained {xp_gain} XP.")

        # Quest progress
        for npc in npcs.values():
            quest = npc.get("quest")
            if quest and not quest.get("completed", False):
                if quest.get("type") == "kill" and quest.get("target") == monster.name:
                    quest["progress"] = quest.get("progress", 0) + 1
                    if quest["progress"] >= quest["count"]:
                        quest["completed"] = True

        if leveled_up:
            stdscr.addstr(1, 0, f"You leveled up to level {stats['level']}! +5 skill points!")
        stdscr.refresh()
        stdscr.getch()
        return True
    else:
        lost_xp = stats["xp"] // 2
        stats["xp"] -= lost_xp
        stdscr.addstr(0, 0, f"You were defeated by the {monster.name}...")
        stdscr.addstr(1, 0, f"You lost {lost_xp} XP and will respawn at the starting point.")
        stdscr.refresh()
        stdscr.getch()
        return False

def skill_menu(stdscr, skills):
    """Display all skills with detailed information."""
    pos = 0
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "== Skills ==")
        stdscr.addstr(1, 0, "Use UP/DOWN to scroll, 'b' to go back.")

        if not skills:
            stdscr.addstr(3, 0, "You have no skills yet.")
        else:
            # Show one skill at a time (could expand to multiple later)
            skill = skills[pos]
            stdscr.addstr(3, 0, f"Name: {skill.custom_name} (Original: {skill.name})")
            stdscr.addstr(4, 0, f"Rank: {skill.rank}")
            stdscr.addstr(5, 0, f"Type: {skill.skill_type}")
            stdscr.addstr(6, 0, f"Mana Cost: {skill.mana_cost}")
            stdscr.addstr(7, 0, f"Stamina Cost: {skill.stamina_cost}")
            stdscr.addstr(8, 0, f"Cooldown: {skill.cooldown} turns")
            stdscr.addstr(9, 0, f"Required Class: {skill.required_class or 'None'}")
            stdscr.addstr(10, 0, f"Level Required: {skill.level_required}")
            stdscr.addstr(11, 0, f"Passive: {'Yes' if skill.passive else 'No'}")
            stdscr.addstr(13, 0, f"Description: {skill.description}")

            stdscr.addstr(15, 0, f"[{pos+1}/{len(skills)}]")

        stdscr.refresh()
        key = stdscr.getch()

        if key == ord('b'):
            break
        elif key == curses.KEY_UP and skills:
            pos = (pos - 1) % len(skills)
        elif key == curses.KEY_DOWN and skills:
            pos = (pos + 1) % len(skills)

#This is the upgrade menu, when you have skill points
def upgrade_menu(stdscr, stats):
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "== Upgrade Stats ==")
        stdscr.addstr(1, 0, f"Skill Points: {stats['skill_points']}")
        stdscr.addstr(2, 0, f"1. HP     = {stats['hp']}")
        stdscr.addstr(3, 0, f"2. Attack = {stats['attack']}")
        stdscr.addstr(4, 0, f"3. Defense= {stats['defense']}")
        stdscr.addstr(5, 0, f"4. Speed  = {stats['speed']}")
        stdscr.addstr(6, 0, f"5. Mana   = {stats['mana']}")
        stdscr.addstr(7, 0, f"6. Level  = {stats['level']} | XP: {stats['xp']}/{stats['level']*10}")
        stdscr.addstr(9, 0, "Press 1-5 to upgrade a stat, or 'b' to go back.")
        stdscr.refresh()
        key = stdscr.getch()

        if key == ord('b'):
            break
        elif key in [ord('1'), ord('2'), ord('3'), ord('4'), ord('5')]:
            if stats["skill_points"] > 0:
                if key == ord('1'):
                    stats["hp"] += 2
                elif key == ord('2'):
                    stats["attack"] += 1
                elif key == ord('3'):
                    stats["defense"] += 1
                elif key == ord('4'):
                    stats["speed"] += 1
                elif key == ord('5'):
                    stats["mana"] += 2  # Mana boost amount
                stats["skill_points"] -= 1

#This is the start menu
def start_menu(stdscr):
    curses.curs_set(0)
    stdscr.clear()
    options = ["New Game", "Load Game", "Quit"]
    selected = 0
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "== Welcome to the RPG Game ==")
        stdscr.addstr(1, 0, "Use UP/DOWN arrows and ENTER to select.")
        for i, option in enumerate(options):
            if i == selected:
                stdscr.addstr(3 + i, 0, f"> {option}")
            else:
                stdscr.addstr(3 + i, 0, f"  {option}")
        stdscr.refresh()
        key = stdscr.getch()
        if key == curses.KEY_UP:
            selected = (selected - 1) % len(options)
        elif key == curses.KEY_DOWN:
            selected = (selected + 1) % len(options)
        elif key in [10, 13]:
            return options[selected]

def inventory_menu(stdscr, inventory, stats):
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "== Inventory ==")
        stdscr.addstr(0, 50, "== Currency ==")
        stdscr.addstr(1, 50, f"Gold: {stats['gold']}")

        if not inventory:
            stdscr.addstr(1, 0, "Your inventory is empty.")
        else:
            for i, item in enumerate(inventory):
                suffix = " (W)" if stats.get("wielded_index") == i else ""
                stdscr.addstr(i + 1, 0, f"{i + 1}. {item.name}{suffix}")

        stdscr.addstr(len(inventory) + 2, 0, "Press number to wield/unwield an item.")
        stdscr.addstr(len(inventory) + 3, 0, "Press 'b' to go back.")
        stdscr.refresh()

        key = stdscr.getch()

        if key == ord('b'):
            break

        if ord('1') <= key <= ord(str(min(len(inventory), 9))):
            index = key - ord('1')

            if stats.get("wielded_index") == index:
                stats["wielded_index"] = None
            else:
                stats["wielded_index"] = index

def help_menu(stdscr):
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "== Help Menu ==")
        stdscr.addstr(1,0, "The purpose of this game is to level up characters 'till infinity and beyond.")
        stdscr.addstr(2,0, "'P' on the map stands for the player, 'B' stands for bushes, and 'N' stands for bushes. There will be monsters in bushes.")
        stdscr.addstr(3,0, "You cannot control the battles, but you can choose when to use select skills.")
        stdscr.addstr(5,0,"Press 'b' to go back.")
        stdscr.refresh()
        key = stdscr.getch()

        if key == ord('b'):
            break

# === Global NPC dictionary with quests ===
npcs = {
    (0, 1): {
        "dialogue": "A youngster tells you, 'Slimes are tricky to catch, so I guess I'll play with their corpses.'",
        "quest": {
            "type": "kill", "target": "Slime", "count": 3,
            "progress": 0, "reward": {"xp": 20, "skill_points": 0},
            "completed": False
        }
    },
    (10, 9): {
        "dialogue": "A frail old man tells you, 'If you give me 2 goblin heads, I will give you a reward.'",
        "quest": {
            "type": "kill", "target": "Goblin", "count": 2,
            "progress": 0, "reward": {"xp": 40, "skill_points": 0},
            "completed": False
        }
    },
    (-5, -4): {
        "dialogue": "An agitated farmer paces back in forth, muttering, 'Those disgusting orcs...' ",
        "quest": {
            "type": "kill", "target": "Orc", "count": 1,
            "progress": 0, "reward": {"xp": 100, "skill_points": 1},
            "completed": False
        }
    },
    (-1, 0): {
        "dialogue": "A wizened figure stands, staff in hand: 'You want to follow the path of magic?' ",
        "quest": {
            "type": "class", "class_name": "Mage",
            "accepted": False, "completed": False
        }
    },
    (1, 0): {
        "dialogue": "A rugged veteran sits, hair in the wind, 'Fight like a warrior.' ",
        "quest": {
            "type": "class", "class_name": "Swordsman",
            "accepted": False, "completed": False
        }
    },
    (0,-1): {
        "dialogue": "A kind old man gazes at you warmly, 'May He be with you.' ",
        "quest": {
            "type": "class", "class_name": "Cleric",
            "accepted": False, "completed": False
        }
    },
    
    (0, 4): {
        "dialogue": "A merchant shows off their sales",
        "quest": {
            "type": "gold"
        }
    }


}

#This sets the cursor state
def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(0)
    stdscr.keypad(True)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)

    #Determines the minimal screen size, or it crashes.
    viewport_width, viewport_height = 20, 10
    world = {}

    bush_zones = {
        "slime": {
            "tiles": [(1, 1), (1, 2), (2, 0), (2, 1), (2, 2), (3, 0), (3, 1),
                    (3, 2), (1,3), (1,4), (2,3), (2,4), (3,3), (3,4), (4,2),
                    (4,3), (5,3), (6,3), (7,3), (5,2), (6,2)],
            "level_range": (1, 3)
        },
        "goblin": {
            "tiles": [(-5, -5), (-5, -6), (-6, -5), (-6, -6)],
            "level_range": (4, 6)
        },
        "orc": {
            "tiles": [(10, 10), (10, 11), (11, 10), (11, 11)],
            "level_range": (8, 12)
        },
        "mixed": {
            "tiles": [(8, -3), (8, -4), (9, -3), (9, -4)],
            "level_range": (5, 10)
        }
    }

    landmarks = {
        'B': sum((zone["tiles"] for zone in bush_zones.values()), []),  # all bushes
        '*': [(0, 0)],
        'W': [(x, 0) for x in range(-20, 21)] + [(0, y) for y in range(-20, 21)]
    }

    choice = start_menu(stdscr)
    if choice == "Load Game":
        loaded = load_game()
        if loaded:
            stats, player_x, player_y = loaded
            inventory = []  # if you want inventory persistence, load it too later
        else:
            stdscr.addstr(0, 0, "No save found. Starting new game.")
            stdscr.refresh()
            time.sleep(1)
            stats, inventory, player_x, player_y = new_game()
    elif choice == "New Game":
        stats, inventory, player_x, player_y = new_game()
    elif choice == "Quit":
        return

    #This gets the landmarks to put on the grid.
    
    def get_landmark_at(x, y):
        for icon, pos in landmarks.items():
            if (x, y) in pos:
                return icon
        return None

    #This picks the monsters to battle the user
    def pick_monster(monsters):
        total = sum(chance for _, chance in monsters)
        r = random.random() * total
        upto = 0
        for monster, chance in monsters:
            if upto + chance >= r:
                return monster
            upto += chance
        return monsters[-1][0]
    
    #This sets up the map
    while True:
        stdscr.clear()
        top_left_x = player_x - viewport_width // 2
        top_left_y = player_y - viewport_height // 2

        for y in range(viewport_height):
            for x in range(viewport_width):
                world_x = top_left_x + x
                world_y = top_left_y + y
                screen_x = x * 2
                if (world_x, world_y) == (player_x, player_y):
                    stdscr.addstr(y, screen_x, "P ")
                elif (world_x, world_y) in npcs:
                    stdscr.addstr(y, screen_x, "N ")
                else:
                    icon = get_landmark_at(world_x, world_y)
                    if icon == 'W':
                        stdscr.addstr(y, screen_x, ". ", curses.color_pair(1))
                    elif icon:
                        stdscr.addstr(y, screen_x, icon + " ")
                    else:
                        stdscr.addstr(y, screen_x, world.get((world_x, world_y), ".") + " ")

        stdscr.addstr(viewport_height + 1, 0, f"Level: {stats['level']} XP: {stats['xp']}/{stats['level'] * 10} Skill Pts: {stats['skill_points']}")
        stdscr.addstr(viewport_height + 2, 0, "Arrows = move | q = quit | u = upgrade | i = inventory | k = skill rename | p = skill window | s = save | l = load | h = help")

        #This is the npc part
        if (player_x, player_y) in npcs:
                    npc = npcs[(player_x, player_y)]
                    stdscr.addstr(viewport_height + 3, 0, npc["dialogue"])
                    quest = npc.get("quest")
                    if quest:
                        if quest["type"] == "class":
                            if stats["class_path"] is None:
                                if not quest["accepted"]:
                                    stdscr.addstr(viewport_height + 4, 0, f"Do you want to become a {quest['class_name']}? Press 'y' to accept.")
                                    stdscr.refresh()
                                    key = stdscr.getch()
                                    if key == ord('y'):
                                        quest["accepted"] = True
                                        stats["class_path"] = quest["class_name"]
                                        stdscr.addstr(viewport_height + 5, 0, f"You are now on the path of the {quest['class_name']}!")
                                        stdscr.getch()
                                else:
                                    stdscr.addstr(viewport_height + 4, 0, f"Class quest: Prove yourself to become a {quest['class_name']}.")
                            else:
                                if stats["class_path"] != quest["class_name"]:
                                    stdscr.addstr(viewport_height + 4, 0, "You have chosen a different path. You cannot become this class.")
                                else:
                                    stdscr.addstr(viewport_height + 4, 0, f"Continue your path as a {stats['class_path']}.")

                        elif quest["completed"] and not quest.get("reward_given", False):
                            reward = quest["reward"]
                            stats["xp"] += reward["xp"]
                            stats["skill_points"] += reward["skill_points"]
                            npc["reward_given"] = True
                            stdscr.addstr(viewport_height + 4, 0, f"Quest complete! +{reward['xp']} XP, +{reward['skill_points']} SP!")
                            leveled_up = gain_xp(stats, 0)
                            if leveled_up:
                                stdscr.addstr(viewport_height + 5, 0, f"You leveled up to level {stats['level']}! +5 SP!")
                            quest["completed"] = False
                            quest["progress"] = 0
                        elif not quest["completed"]:
                            stdscr.addstr(viewport_height + 4, 0, f"Quest: Defeat {quest['count']} {quest['target']}s [{quest['progress']}/{quest['count']}]")



        stdscr.refresh()
        world[(player_x, player_y)] = '.'
        key = stdscr.getch()


        player_skills = []

        # Later in the code, after choosing a class
        if stats["class_path"] == "Swordsman":
            player_skills.extend([
                Skill("Power Strike", "Empowers your next attack to do 2.5x the damage.", "active", mana_cost=0, stamina_cost = 3, cooldown=5, required_class="Swordsman", rank="C", level_required=1, effect = "damage_buff", duration = 1, power = 2.5),
                Skill("Quick Jab", "A fast, weak jab drops the opposing parties defense by 0.1.", "active", mana_cost=0, stamina_cost = 2, cooldown=3, required_class="Swordsman", rank="D", level_required=1, effect = "mons_defense_debuff", duration = 2, power = 0.8),
            ])
        elif stats["class_path"] == "Mage":
            player_skills.extend([
                Skill("Fireball", "A ball of fire.", "active", mana_cost=8, stamina_cost = 1, cooldown=7, required_class="Mage", rank="C", level_required=1, effect = "damage_buff", duration = 2, power = 1.5),
                Skill("Arcane Bolt", "A bolt of arcane energy.", "active", mana_cost=4, stamina_cost = 1, cooldown=6, required_class="Mage", rank="D", level_required=1, effect = "damage_buff", duration = 1, power = 1.6),
            ])
        
        elif stats["class_path"] == "Cleric":
            player_skills.extend([
                Skill("Heal", "A pulse of holy light heals allies.", "active", mana_cost=10, stamina_cost = 1, cooldown=2, required_class="Cleric", rank="C", level_required=1, effect = "hp_buff", duration = 1, power = None),
                Skill("Purify", "A pulse of holy light weakens enemies.", "active", mana_cost=8, stamina_cost = 1, cooldown=5, required_class="Cleric", rank="D", level_required=1, effect = "damage_buff", duration = 1, power = 1.2),
            ])


        #These are the commands to quit, upgrade, save, and load
        if key == ord('q'):
            break
        elif key == ord('u'):
            upgrade_menu(stdscr, stats)
        elif key == ord('i'):
            inventory_menu(stdscr, inventory, stats)
        elif key == ord('s'):
            save_game(stats, player_x, player_y)
        elif key == ord('p'):
            skill_menu(stdscr, player_skills)
        elif key == ord('h'):
            help_menu(stdscr)
        elif key == ord('k'):  # or any unused key
            rename_skill_menu(stdscr, player_skills)
        elif key == ord('l'):
            loaded = load_game()
            if loaded:
                stats, player_x, player_y = loaded
        #These determine the moves of the user
        elif key == curses.KEY_UP:
            player_y -= 1
        elif key == curses.KEY_DOWN:
            player_y += 1
        elif key == curses.KEY_LEFT:
            player_x -= 1
        elif key == curses.KEY_RIGHT:
            player_x += 1

        current_tile = (player_x, player_y)

        # Only trigger battle if in a bush zone
        for zone_name, zone in bush_zones.items():
            if current_tile in zone["tiles"]:
                level_range = zone["level_range"]

                # Determine monster list and spawn chance
                if zone_name == "slime":
                    if random.random() < 0.20:
                        if not battle(stdscr, "Slime", stats, inventory, player_skills, level_range):
                            player_x, player_y = 0, 0
                elif zone_name == "goblin":
                    if random.random() < 0.10:
                        if not battle(stdscr, "Goblin", stats, inventory, player_skills, level_range):
                            player_x, player_y = 0, 0
                elif zone_name == "orc":
                    if random.random() < 0.08:
                        if not battle(stdscr, "Orc", stats, inventory, player_skills, level_range):
                            player_x, player_y = 0, 0
                elif zone_name == "mixed":
                    if random.random() < 0.15:
                        monsters = [("Slime", 0.4), ("Goblin", 0.3), ("Kobold", 0.2), ("Orc", 0.1)]
                        chosen = pick_monster(monsters)
                        if not battle(stdscr, chosen, stats, inventory, player_skills, level_range):
                            player_x, player_y = 0, 0
                break  # Only one zone can apply
            
#Starts the game
curses.wrapper(main)