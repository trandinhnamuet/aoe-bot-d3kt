"""Bot names (the user, 20/10). A bot whose seat is Random parks under a generic name - a title and an animal,
English or Vietnamese (ASCII, the game's name field has no accents): "Duke Falcon", "Te Tuong Ho",
"Hoang De Su Tu". A seat with a chosen civ gets "<Civ> <noun>" - "Yamato Samurai", "Roman Caesar" - from the
civ's own nouns first, then the shared titles and animals. Names stay within NAME_MAX characters (the game's
name field) and never repeat among the bots of one launcher."""
import random

import lobby

NAME_MAX = 16

# nouns of each civilisation (the first ones are the civ's own flavour)
NOUNS = {
    "Egyptian": ["Pharaoh", "Sphinx", "Nile", "Anubis", "Ramses", "Horus"],
    "Greek": ["Hoplite", "Spartan", "Athena", "Zeus", "Achilles", "Hermes"],
    "Babylonian": ["Lion", "Gate", "King", "Ishtar", "Marduk"],
    "Assyrian": ["Archer", "Nineveh", "Ashur", "Bow", "Sargon"],
    "Minoan": ["Bowman", "Knossos", "Minos", "Bull", "Crete"],
    "Hittite": ["Chariot", "Hattusa", "Storm", "Iron", "Anatol"],
    "Phoenician": ["Tyre", "Ship", "Cedar", "Sidon", "Byblos"],
    "Sumerian": ["Ur", "Uruk", "Enki", "Reed", "Lagash"],
    "Persian": ["Immortal", "Cyrus", "Darius", "Xerxes", "Lion"],
    "Shang": ["Emperor", "Dragon", "Tiger", "Yin", "Anyang"],
    "Yamato": ["Samurai", "Shogun", "Ronin", "Ninja", "Daimyo"],
    "Choson": ["Legion", "Tiger", "Hwarang", "Han", "Silla"],
    "Roman": ["Legion", "Caesar", "Eagle", "Scipio", "Consul"],
    "Carthaginian": ["Ox", "Ram", "Fox", "Sea"],                  # (12 letters: 3-letter nouns only)
    "Palmyran": ["Camel", "Zenobia", "Oasis", "Sun", "Desert"],
    "Macedonian": ["Phalanx", "Lion", "Argead", "Pella"],
}

# shared titles and animals, English and Vietnamese (no accents)
TITLES_EN = ["Emperor", "King", "Queen", "Prince", "Duke", "Count", "Baron", "Marquis", "Knight", "Marshal",
             "General", "Admiral", "Chancellor", "Consul", "Senator", "Sultan", "Khan", "Shogun", "Pharaoh", "Caesar",
             "Lord", "Warlord", "Captain", "Chief"]
ANIMALS_EN = ["Lion", "Tiger", "Wolf", "Eagle", "Falcon", "Hawk", "Bear", "Fox", "Dragon", "Elephant", "Cobra",
              "Shark", "Panther", "Leopard", "Jaguar", "Rhino", "Bison", "Stag", "Raven", "Viper", "Scorpion", "Lynx",
              "Puma", "Crane", "Phoenix", "Hound", "Mustang", "Bull", "Boar", "Owl", "Condor", "Mamba", "Hornet"]
TITLES_VN = ["Hoang De", "Vua", "Chua", "Hoang Tu", "Thai Tu", "Te Tuong", "Ba Tuoc", "Cong Tuoc", "Hau Tuoc",
             "Nam Tuoc", "Tu Tuoc", "Tuong Quan", "Dai Tuong", "Nguyen Soai", "Quan Cong", "Thu Linh", "Lanh Chua",
             "Hiep Si", "Dai Vuong", "Thuong Tuong", "Do Doc"]
ANIMALS_VN = ["Su Tu", "Ho", "Soi", "Dai Bang", "Gau", "Cao", "Rong", "Voi", "Ran", "Bao", "Te Giac", "Trau", "Huou",
              "Qua", "Bo Cap", "Ngua", "Ca Map", "Phuong Hoang", "Ho Mang", "Chim Ung", "Ky Lan", "Hac", "Cu",
              "Bao Den", "Soi Xam", "Ho Trang"]
TITLES = TITLES_EN + TITLES_VN
ANIMALS = ANIMALS_EN + ANIMALS_VN


def random_civ():
    """A civ index (1..16) drawn by the launcher instead of the game, so the bot can be named for it."""
    return random.randint(1, len(lobby.CIVS))


def _fits(name, used):
    return len(name) <= NAME_MAX and name not in used


def generic_name(used):
    """"<Title> <Animal>" for a Random seat, not in `used`; numbered when the pool is exhausted."""
    for _ in range(200):
        # one language per name: "Duke Falcon" or "Te Tuong Ho", never "Lord Gau"
        titles, animals = random.choice(((TITLES_EN, ANIMALS_EN), (TITLES_VN, ANIMALS_VN)))
        n = "%s %s" % (random.choice(titles), random.choice(animals))
        if _fits(n, used):
            return n
    k = 2
    while True:
        n = "Bot %d" % k
        if n not in used:
            return n
        k += 1


def name_for(civ, used):
    """"<Civ> <noun>" for a chosen civ: the civ's own nouns first, then the shared animals and titles (shuffled),
    the first one not in `used` that fits NAME_MAX; numbered when every noun is taken."""
    cname = lobby.CIVS[civ - 1] if 1 <= civ <= len(lobby.CIVS) else "AI"
    shared = ANIMALS + TITLES
    random.shuffle(shared)
    for noun in NOUNS.get(cname, []) + shared:
        n = "%s %s" % (cname, noun)
        if _fits(n, used):
            return n
    k = 2
    while True:
        n = "%s %d" % (cname[:NAME_MAX - 2], k)
        if n not in used:
            return n
        k += 1
