/*
 * Category management (#/categories): create, rename, delete.
 *
 * Deleting a category in use first lists its recipes; they keep
 * existing without a category.
 */

import * as API from "./api.js";
import { h, toast, error_msg, back_button, topbar } from "./form.js";

function count_text(n)
{
	return n === 1 ? "1 Rezept" : n + " Rezepte";
}

function same_name(a, b)
{
	return a.trim().toLowerCase() === b.trim().toLowerCase();
}

function name_input(value)
{
	return h("input", { name: "name", value: value, required: true,
			    maxlength: 200, autocomplete: "off",
			    "aria-label": "Name" });
}

/*
 * Confirmation sheet; resolves true for «Löschen», false otherwise.
 */
function confirm_sheet(text, recipes, ok_label)
{
	return new Promise((resolve) => {
		const done = (v) => {
			box.remove();
			resolve(v);
		};
		const item = (r) => h("li", {},
			h("a", { href: "#/recipe/" + r.id,
				 onclick: () => done(false) }, r.title));
		const list = recipes.length === 0 ? null :
			h("ul", { class: "cat-recipes" }, recipes.map(item));
		const box = h("div", { class: "sheet-bg", onclick: (ev) => {
			if (ev.target === box)
				done(false);
		} },
			h("div", { class: "sheet", role: "dialog" },
				h("p", {}, text), list,
				h("button", { type: "button",
					      class: "btn-danger",
					      onclick: () => done(true) },
				  ok_label),
				h("button", { type: "button",
					      onclick: () => done(false) },
				  "Abbrechen")));
		document.body.append(box);
	});
}

async function ask_delete(c)
{
	if (c.recipe_count === 0)
		return confirm_sheet("Kategorie «" + c.name + "» löschen?",
				     [], "Löschen");
	const recipes = await API.category_recipes(c.id);
	const n = recipes.length;
	const text = "«" + c.name + "» wird noch von " +
		(n === 1 ? "1 Rezept" : n + " Rezepten") +
		" verwendet. Sie bleiben erhalten, aber ohne Kategorie.";
	return confirm_sheet(text, recipes, "Trotzdem löschen");
}

export async function view_categories()
{
	let cats = await API.list_categories();
	let editing = null;
	const ul = h("ul", { class: "shop cats" });

	const reload = async () => {
		cats = await API.list_categories();
		draw();
	};
	const taken = (name, id) =>
		cats.find(c => c.id !== id && same_name(c.name, name));

	const remove = async (c) => {
		try {
			if (!await ask_delete(c))
				return;
			await API.delete_category(c.id);
			toast("Kategorie gelöscht", false);
			await reload();
		} catch (e) {
			toast(error_msg(e), true);
		}
	};

	const rename = async (c, name) => {
		name = name.trim();
		if (name === "")
			return;
		const other = taken(name, c.id);
		if (other) {
			toast("«" + other.name + "» gibt es schon", true);
			return;
		}
		try {
			await API.rename_category(c.id, name);
			editing = null;
			await reload();
		} catch (e) {
			toast(error_msg(e), true);
		}
	};

	const edit_line = (c) => {
		const input = name_input(c.name);
		const form = h("form", { class: "row", onsubmit: (ev) => {
			ev.preventDefault();
			rename(c, input.value);
		} }, input,
			h("button", { type: "submit",
				      class: "btn btn-primary" }, "Speichern"),
			h("button", { type: "button", class: "btn",
				      onclick: () => {
				editing = null;
				draw();
			} }, "Abbrechen"));
		setTimeout(() => input.focus(), 0);
		return h("li", { class: "item" }, form);
	};

	const line = (c) => {
		if (editing === c.id)
			return edit_line(c);
		return h("li", { class: "item" },
			h("span", { class: "text" }, c.name,
				h("span", { class: "note" },
				  " · " + count_text(c.recipe_count))),
			h("button", { type: "button", class: "btn-link",
				      onclick: () => {
				editing = c.id;
				draw();
			} }, "Umbenennen"),
			h("button", { type: "button", class: "del btn-danger",
				      "aria-label": "Löschen",
				      onclick: () => remove(c) }, "✕"));
	};

	const draw = () => {
		ul.replaceChildren(...cats.map(line));
		if (cats.length === 0)
			ul.append(h("li", { class: "empty" },
				     "Keine Kategorien"));
	};

	const input = name_input("");
	input.placeholder = "Neue Kategorie";
	const form = h("form", { class: "shop-add", onsubmit: async (ev) => {
		ev.preventDefault();
		const name = input.value.trim();
		if (name === "")
			return;
		const other = taken(name, null);
		if (other) {
			toast("«" + other.name + "» gibt es schon", true);
			return;
		}
		try {
			await API.create_category(name);
			input.value = "";
			await reload();
		} catch (e) {
			toast(error_msg(e), true);
		}
	} }, h("div", { class: "row" }, input,
		h("button", { type: "submit", class: "btn btn-primary" },
		  "Anlegen")));

	draw();
	return h("div", {},
		topbar("Kategorien", back_button("#/")),
		h("main", {}, ul, form));
}
