"""schema.org/Recipe extraction from microdata."""

from decimal import Decimal

from app.importer import microdata
from app.services.importer import _extract

PAGE = """
<html><head><title>Omelette - Rezept | Beispiel</title>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "HowTo", "name": "Omelette"}
</script></head><body>
<ul class="nav"><li>1 Rezept</li><li>2 Rezepte</li><li>3 Rezepte</li></ul>
<div itemscope itemtype="http://schema.org/Recipe">
	<span itemprop="name">Omelette</span>
	<meta itemprop="image" content="https://example.org/gross.jpg">
	<meta itemprop="image" content="https://example.org/klein.jpg">
	<div itemprop="description">Schnell gemacht.</div>
	<div itemprop="recipeYield">2 Portionen</div>
	<meta content="PT15M" itemprop="prepTime">
	<table>
	<tr itemprop="recipeIngredient"><td><span>150</span><span>
	g</span></td><th>Mehl</th></tr>
	<tr itemprop="recipeIngredient"><td><span>2,5</span><span>
	dl</span></td><th>Milch</th></tr>
	<tr itemprop="recipeIngredient"><td></td><th>Salz</th></tr>
	</table>
	<ol>
	<li itemprop="recipeInstructions" itemscope
	    itemtype="http://schema.org/HowToStep">
		<span itemprop="text">Verrühren.</span></li>
	<li itemprop="recipeInstructions" itemscope
	    itemtype="http://schema.org/HowToStep">
		<span itemprop="text">Backen.</span></li>
	</ol>
	<div itemprop="nutrition" itemscope
	     itemtype="http://www.schema.org/NutritionInformation">
		<span itemprop="calories">378</span>kcal,
		<span itemprop="fatContent">18</span>g,
		<span itemprop="carbohydrateContent">42</span>g,
		<span itemprop="proteinContent">11</span>g
	</div>
</div>
</body></html>
"""


def test_fields():
	data = microdata.extract(PAGE)
	assert data.title == "Omelette"
	assert data.intro == "Schnell gemacht."
	assert data.servings == 2
	assert data.prep_minutes == 15
	assert data.image_url == "https://example.org/gross.jpg"


def test_ingredients_and_steps():
	data = microdata.extract(PAGE)
	assert data.ingredient_lines == ["150 g Mehl", "2,5 dl Milch", "Salz"]
	assert data.steps == ["Verrühren.", "Backen."]


def test_nutrition():
	data = microdata.extract(PAGE)
	assert data.kcal == Decimal("378.0")
	assert data.fat_g == Decimal("18.0")
	assert data.carbs_g == Decimal("42.0")
	assert data.protein_g == Decimal("11.0")


def test_nested_item_keeps_its_own_properties():
	html = """<div itemscope itemtype="https://schema.org/Recipe">
		<span itemprop="name">Aussen</span>
		<div itemprop="author" itemscope
		     itemtype="https://schema.org/Person">
			<span itemprop="name">Innen</span></div>
		</div>"""
	assert microdata.extract(html).title == "Aussen"


def test_no_recipe():
	assert microdata.extract("<html><body><p>Text</p></body></html>"
				 ) is None
	assert microdata.extract(
		'<div itemscope itemtype="https://schema.org/Person"></div>'
		) is None


def test_recipe_with_body_wins():
	html = """<div itemscope itemtype="https://schema.org/Recipe">
		<span itemprop="name">Leer</span></div>
		<div itemscope itemtype="https://schema.org/Recipe">
		<span itemprop="name">Voll</span>
		<div itemprop="recipeIngredient">1 Ei</div></div>"""
	assert microdata.extract(html).title == "Voll"


def test_microdata_used_when_json_ld_has_no_recipe():
	data, method = _extract(PAGE)
	assert method == "microdata"
	assert data.title == "Omelette"


def test_json_ld_recipe_wins_over_microdata():
	script = ('<script type="application/ld+json">{"@type": "Recipe", '
		  '"name": "LD", "recipeIngredient": ["1 Ei"]}</script>')
	data, method = _extract(script + PAGE)
	assert method == "jsonld"
	assert data.title == "LD"
