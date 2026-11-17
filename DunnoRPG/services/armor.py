def armor_by_durability(armor, durability):
    """Extra durability delays armor loss without raising the item's armor."""
    durability = int(durability)
    if durability <= 0:
        return 0
    # Armor 5 lasts through durability 200; it drops to 4 at 199.
    return min(armor, durability // 50 + 1)
