import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from process.resolution import Attribute, Skill
from engine import GameState, Item

def verify_combat():
    print("Initializing Combat Verification...")
    game = GameState()
    
    # 1. Setup Combatants
    attacker = game.player # MacReady
    target = next(m for m in game.crew if m.name == "Childs")
    
    # Ensure they are in said locations for context, though combat doesn't enforce range strictly in code yet
    attacker.location = (5,5)
    target.location = (5,5)
    
    # 2. Test Inventory / Weapon Equip
    print("\n[Test] Equipping Weapon...")
    flamethrower = Item("Flamethrower", "Burn.", weapon_skill=Skill.FIREARMS, damage=3)
    attacker.add_item(flamethrower)
    print(f"Added {flamethrower.name} to {attacker.name}")
    
    weapon_found = next((i for i in attacker.inventory if i.damage > 0), None)
    if weapon_found:
        print(f"Verified Weapon Found: {weapon_found.name} (Dmg {weapon_found.damage})")
    else:
        print("FAIL: Weapon not found in inventory.")
        return

    # 3. Simulate Attack Roll
    print("\n[Test] Simulating Attack Round...")
    
    # Attacker stats
    att_skill = weapon_found.weapon_skill
    att_attr = Skill.get_attribute(att_skill)
    print(f"Attacker rolling {att_attr.value} + {att_skill.value}")
    
    att_res = attacker.roll_check(att_attr, att_skill)
    print(f"Attacker Hits: {att_res['success_count']} (Dice: {att_res['dice']})")
    
    # Defender stats
    def_res = target.roll_check(Attribute.PHYSICAL, Skill.MELEE)
    print(f"Defender Hits: {def_res['success_count']} (Dice: {def_res['dice']})")
    
    # Damage Calc
    target_start_hp = target.health
    print(f"Target HP: {target_start_hp}")
    
    if att_res['success_count'] > def_res['success_count']:
        net = att_res['success_count'] - def_res['success_count']
        dmg = weapon_found.damage + net
        print(f"Hit! Damage: {dmg}")
        died = target.take_damage(dmg)
        print(f"Target New HP: {target.health}")
        if target.health != target_start_hp - dmg and target.health != 0:
             print(f"FAIL: HP Math incorrect. Expected {target_start_hp - dmg}, got {target.health}")
    else:
        print("Miss/Blocked.")
        if target.health != target_start_hp:
             print("FAIL: HP changed on miss.")

    print("\nCombat Verification Complete.")

if __name__ == "__main__":
    verify_combat()
