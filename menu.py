"""The cafe menu. The bot and the page both read this, so they always agree."""

CAFE_NAME = "Sunday Bakehouse"

SECTIONS = {
    "coffee": "Coffee",
    "tea": "Tea & more",
    "pastries": "Pastries",
    "breakfast": "Breakfast",
}

TAGS = {
    "vegan": "Vegan",
    "dairy-free": "Dairy-free",
    "gluten-free": "Gluten-free",
    "caffeine-free": "Caffeine-free",
}

ITEMS = [
    {"id": "espresso", "section": "coffee", "name": "Espresso", "price": 3.25, "tags": ["vegan", "dairy-free", "gluten-free"], "about": "Double shot of our house blend. Chocolate and cherry notes."},
    {"id": "cortado", "section": "coffee", "name": "Cortado", "price": 4.25, "tags": ["gluten-free"], "about": "Equal parts espresso and steamed milk."},
    {"id": "oat-latte", "section": "coffee", "name": "Oat Milk Latte", "price": 5.50, "tags": ["vegan", "dairy-free", "gluten-free"], "about": "Our most popular drink. Creamy oat milk, double shot."},
    {"id": "cold-brew", "section": "coffee", "name": "Cold Brew", "price": 4.75, "tags": ["vegan", "dairy-free", "gluten-free"], "about": "Steeped 18 hours. Smooth and strong."},
    {"id": "honey-cardamom", "section": "coffee", "name": "Honey Cardamom Latte", "price": 6.00, "tags": ["gluten-free"], "about": "Seasonal. Local honey, cardamom, whole milk."},
    {"id": "matcha", "section": "tea", "name": "Matcha Latte", "price": 5.75, "tags": ["gluten-free"], "about": "Ceremonial matcha whisked with milk."},
    {"id": "chai", "section": "tea", "name": "Spiced Chai", "price": 5.25, "tags": ["gluten-free"], "about": "House chai concentrate with cinnamon and ginger."},
    {"id": "hot-chocolate", "section": "tea", "name": "Hot Chocolate", "price": 4.50, "tags": ["caffeine-free", "gluten-free"], "about": "Dark chocolate, whole milk, sea salt."},
    {"id": "mint-tea", "section": "tea", "name": "Fresh Mint Tea", "price": 3.75, "tags": ["vegan", "dairy-free", "gluten-free", "caffeine-free"], "about": "Fresh mint leaves and hot water. That's it."},
    {"id": "croissant", "section": "pastries", "name": "Butter Croissant", "price": 4.25, "tags": [], "about": "Laminated for three days. Flaky and rich."},
    {"id": "almond-croissant", "section": "pastries", "name": "Almond Croissant", "price": 5.25, "tags": [], "about": "Twice baked with almond cream."},
    {"id": "morning-bun", "section": "pastries", "name": "Morning Bun", "price": 4.75, "tags": [], "about": "Orange zest, cinnamon sugar. Sells out by 10."},
    {"id": "banana-bread", "section": "pastries", "name": "Vegan Banana Bread", "price": 4.00, "tags": ["vegan", "dairy-free"], "about": "Walnuts and dark chocolate chips."},
    {"id": "gf-brownie", "section": "pastries", "name": "Flourless Brownie", "price": 4.50, "tags": ["gluten-free"], "about": "Fudgy, made with almond flour."},
    {"id": "avocado-toast", "section": "breakfast", "name": "Avocado Toast", "price": 11.00, "tags": ["vegan", "dairy-free"], "about": "Sourdough, chili flakes, lemon, sesame."},
    {"id": "egg-sandwich", "section": "breakfast", "name": "Egg & Cheddar Sandwich", "price": 9.50, "tags": [], "about": "Soft scrambled eggs, aged cheddar, brioche."},
    {"id": "yogurt-bowl", "section": "breakfast", "name": "Yogurt & Granola Bowl", "price": 8.75, "tags": ["gluten-free"], "about": "Greek yogurt, house granola, berries, honey."},
]

ITEMS_BY_ID = {item["id"]: item for item in ITEMS}

# Gift card codes the cafe has sold, and their balances.
GIFT_CARDS = {"SUNDAY-2517": 25.00}


def menu_for_prompt() -> str:
    """The menu as plain lines for the system prompt."""
    lines = []
    for key, title in SECTIONS.items():
        lines.append(f"{title} (section id: {key}):")
        for item in ITEMS:
            if item["section"] != key:
                continue
            tags = ", ".join(item["tags"]) or "none"
            lines.append(f"- {item['name']} (id: {item['id']}) ${item['price']:.2f}. Tags: {tags}. {item['about']}")
    return "\n".join(lines)


def menu_for_page() -> dict:
    return {"cafe": CAFE_NAME, "sections": SECTIONS, "tags": TAGS, "items": ITEMS}
