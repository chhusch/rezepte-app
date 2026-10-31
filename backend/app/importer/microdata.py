"""schema.org/Recipe extraction from HTML microdata (itemprop attributes)."""

from bs4 import BeautifulSoup, Tag

from app.importer.common import RecipeData
from app.importer.jsonld import map_recipe

LIST_PROPS = ("recipeIngredient", "recipeInstructions", "itemListElement")
VALUE_ATTRS = {"meta": "content", "img": "src", "a": "href", "link": "href",
	       "time": "datetime"}
MAX_DEPTH = 8


def _is_recipe(tag: Tag) -> bool:
	types = (tag.get("itemtype") or "").split()
	return any(t.rstrip("/").rsplit("/", 1)[-1].lower() == "recipe"
		   for t in types)


def _text_value(tag: Tag) -> str:
	attr = VALUE_ATTRS.get(tag.name)
	value = tag.get(attr) if attr else None
	return value or " ".join(tag.get_text(" ").split())


def _value(tag: Tag, depth: int):
	if tag.has_attr("itemscope"):
		return _item(tag, depth + 1)
	return _text_value(tag)


def _item(scope: Tag, depth: int = 0) -> dict:
	"""Properties of one itemscope; nested items stay in their own."""
	node: dict = {}
	if depth > MAX_DEPTH:
		return node
	for tag in scope.find_all(itemprop=True):
		if tag.find_parent(itemscope=True) is not scope:
			continue
		for name in tag["itemprop"].split():
			if name in LIST_PROPS:
				node.setdefault(name, []).append(
					_value(tag, depth))
			elif name not in node:
				node[name] = _value(tag, depth)
	return node


def extract(html: str) -> RecipeData | None:
	soup = BeautifulSoup(html, "html.parser")
	nodes = [_item(t) for t in soup.find_all(itemscope=True)
		 if _is_recipe(t)]
	if not nodes:
		return None
	node = next((n for n in nodes if n.get("recipeIngredient")
		     or n.get("recipeInstructions")), nodes[0])
	return map_recipe(node)
