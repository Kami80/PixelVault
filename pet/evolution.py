def add_xp(pet, amount):
    pet.xp += max(0, int(amount))

    while pet.xp >= pet.level * 100:
        pet.level += 1

    pet.save(update_fields=["xp", "level"])
