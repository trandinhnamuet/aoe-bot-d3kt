"""Bot names by civilisation (the user, 20/10): "<Civ> <noun>", e.g. "Yamato Samurai". A civ chosen at random by
the launcher gets its name from the civ it was given, so the room shows what each bot plays. Names stay within
NAME_MAX characters (the game's name field); a second bot of the same civ takes the next noun."""
import random

import lobby

NAME_MAX = 16
NOUNS = {
    "Egyptian": ["Pharaoh", "Sphinx", "Nile", "Anubis"],
    "Greek": ["Hoplite", "Spartan", "Athena", "Zeus"],
    "Babylonian": ["Lion", "Gate", "Ox", "King"],
    "Assyrian": ["Archer", "Nineveh", "Ashur", "Bow"],
    "Minoan": ["Bowman", "Knossos", "Minos", "Bull"],
    "Hittite": ["Chariot", "Hattusa", "Storm", "Iron"],
    "Phoenician": ["Tyre", "Ship", "Cedar", "Ba"],
    "Sumerian": ["Ur", "Uruk", "Enki", "Reed"],
    "Persian": ["Immortal", "Cyrus", "Darius", "Lion"],
    "Shang": ["Emperor", "Dragon", "Tiger", "Yin"],
    "Yamato": ["Samurai", "Shogun", "Ronin", "Ninja"],
    "Choson": ["Legion", "Tiger", "Hwarang", "Han"],
    "Roman": ["Legion", "Caesar", "Eagle", "Scipio"],
    "Carthaginian": ["Ox", "Ram", "Fox", "Sea"],
    "Palmyran": ["Camel", "Zenobia", "Oasis", "Sun"],
    "Macedonian": ["Phalanx", "Alexander", "Argead", "Lion"],
}


def random_civ():
    """A civ index (1..16) drawn by the launcher instead of the game, so the bot can be named for it."""
    return random.randint(1, len(lobby.CIVS))


def name_for(civ, used):
    """The first "<Civ> <noun>" not in `used` that fits NAME_MAX; numbered when every noun is taken."""
    cname = lobby.CIVS[civ - 1] if 1 <= civ <= len(lobby.CIVS) else "AI"
    for noun in NOUNS.get(cname, ["Bot"]):
        n = "%s %s" % (cname, noun)
        if len(n) <= NAME_MAX and n not in used:
            return n
    k = 2
    while True:
        n = "%s %d" % (cname[:NAME_MAX - 2], k)
        if n not in used:
            return n
        k += 1
