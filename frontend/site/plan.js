/*
 * Meal plan (#/plan) and its ingredient list (#/plan/shopping).
 *
 * Four days from today or a week from Monday, paged with ‹ ›. Each
 * day has lunch and dinner, breakfast and zvieri when switched on for
 * that day, a note and a highlight colour. An entry is a recipe or a
 * free text. «Planung abschliessen» lists the ingredients of the
 * shown days to pick what goes on the shopping list.
 */

import * as API from "./api.js";
import {
	h, toast, error_msg, back_button, topbar, fmt_amount, open_sheet,
} from "./form.js";

const VIEW_KEY = "plan:view";
const VIEW_DAYS = { four: 4, week: 7 };
const MAX_HITS = 8;
const WEEKDAYS = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
/* key, label, day flag that switches it on (null: always shown) */
const SLOTS = [
	["breakfast", "Frühstück", "breakfast"],
	["lunch", "Mittagessen", null],
	["zvieri", "Zvieri", "zvieri"],
	["dinner", "Abendessen", null],
];
const COLORS = [
	["razz", "Pink"],
	["mustard", "Senfgelb"],
	["sea", "Grün"],
	["coffee", "Braun"],
];

let view = load_view();
let offset = 0;
let recipe_cache = null;

/* ------------------------------------------------------------------ */
/* Dates                                                               */
/* ------------------------------------------------------------------ */

function pad2(n)
{
	return String(n).padStart(2, "0");
}

function iso(d)
{
	return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" +
	       pad2(d.getDate());
}

function parse_iso(s)
{
	const [y, m, d] = s.split("-").map(Number);
	return new Date(y, m - 1, d);
}

function add_days(d, n)
{
	return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

function today()
{
	const now = new Date();
	return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function monday(d)
{
	return add_days(d, -((d.getDay() + 6) % 7));
}

function short_date(d)
{
	return pad2(d.getDate()) + "." + pad2(d.getMonth() + 1) + ".";
}

function day_label(s)
{
	const d = parse_iso(s);
	const name = iso(d) === iso(today()) ? "Heute" : WEEKDAYS[d.getDay()];
	return name + " " + short_date(d);
}

/* ------------------------------------------------------------------ */
/* View state                                                          */
/* ------------------------------------------------------------------ */

function load_view()
{
	try {
		const v = sessionStorage.getItem(VIEW_KEY);
		return v in VIEW_DAYS ? v : "four";
	} catch (e) {
		return "four";
	}
}

function save_view()
{
	try {
		sessionStorage.setItem(VIEW_KEY, view);
	} catch (e) {
		/* private mode: keep it for this page only */
	}
}

function range()
{
	const days = VIEW_DAYS[view];
	const base = view === "week" ? monday(today()) : today();
	return { start: add_days(base, offset * days), days: days };
}

/* ------------------------------------------------------------------ */
/* Sheets                                                              */
/* ------------------------------------------------------------------ */

async function all_recipes()
{
	if (!recipe_cache)
		recipe_cache = await API.list_recipes();
	return recipe_cache;
}

async function add_entry(entry, done)
{
	try {
		await API.add_plan_entry(entry);
		done();
	} catch (e) {
		toast(error_msg(e), true);
	}
}

function recipe_hits(recipes, q)
{
	const s = q.trim().toLowerCase();
	if (s === "")
		return [];
	return recipes.filter(r => r.title.toLowerCase().includes(s))
		.slice(0, MAX_HITS);
}

function add_sheet(day, slot, label, reload)
{
	const q = h("input", { placeholder: "Rezept suchen oder Notiz",
			       "aria-label": "Rezept oder Notiz",
			       autocomplete: "off" });
	const servings = h("input", { type: "number", min: 1, max: 100,
				      inputmode: "numeric",
				      placeholder: "Portionen",
				      "aria-label": "Portionen" });
	const hits = h("div", { class: "plan-hits" });
	const done = () => {
		close();
		reload();
	};
	const pick = (r) => add_entry({
		day: day, slot: slot, recipe_id: r.id,
		servings: servings.value ? Number(servings.value) : null,
	}, done);
	const as_note = h("button", { type: "button", onclick: () => {
		if (q.value.trim() !== "")
			add_entry({ day: day, slot: slot, text: q.value },
				  done);
	} }, "Als Notiz eintragen");
	q.addEventListener("input", async () => {
		const list = recipe_hits(await all_recipes(), q.value);
		hits.replaceChildren(...list.map(r => h("button", {
			type: "button", class: "plan-hit",
			onclick: () => pick(r) }, r.title)));
	});
	const close = open_sheet(label + ", " + day_label(day),
				 h("div", { class: "row" }, q, servings),
				 hits, as_note);
	q.focus();
}

function color_choice(current)
{
	const cls = (v) => "swatch" + (v ? " mark-" + v : "");
	const opt = (value, name) => h("label", { class: cls(value) },
		h("input", { type: "radio", name: "color", value: value,
			     checked: (current || "") === value }),
		h("span", {}, name));
	return h("div", { class: "swatches" }, opt("", "Keine"),
		 COLORS.map(([v, n]) => opt(v, n)));
}

function day_sheet(d, reload)
{
	const note = h("textarea", { rows: 2, placeholder: "z. B. Gäste",
				     "aria-label": "Tagesnotiz" }, d.note);
	const colors = color_choice(d.color);
	const flag = (name, label) => {
		const box = h("input", { type: "checkbox", name: name,
					 checked: d[name] });
		return h("label", { class: "check" }, box,
			 h("span", {}, label));
	};
	const breakfast = flag("breakfast", "Frühstück");
	const zvieri = flag("zvieri", "Zvieri");
	const save = h("button", { type: "button", class: "btn-primary",
				   onclick: async () => {
		const c = colors.querySelector("input:checked");
		try {
			await API.set_plan_day(d.day, {
				note: note.value,
				color: c && c.value ? c.value : null,
				breakfast: breakfast.querySelector(
					"input").checked,
				zvieri: zvieri.querySelector("input").checked,
			});
			close();
			reload();
		} catch (e) {
			toast(error_msg(e), true);
		}
	} }, "Speichern");
	const close = open_sheet(day_label(d.day), note, colors,
				 breakfast, zvieri, save);
}

/* ------------------------------------------------------------------ */
/* Plan                                                                */
/* ------------------------------------------------------------------ */

function entry_line(e, reload)
{
	const title = e.recipe_id ?
		h("a", { href: "#/recipe/" + e.recipe_id }, e.title) :
		h("span", {}, e.title);
	return h("li", {},
		h("span", { class: "text" }, title,
		  e.servings ? h("span", { class: "note" },
				 " · " + e.servings + " P.") : null),
		h("button", { type: "button", class: "del btn-danger",
			      "aria-label": "Entfernen", onclick: async () => {
			try {
				await API.delete_plan_entry(e.id);
				reload();
			} catch (err) {
				toast(error_msg(err), true);
			}
		} }, "✕"));
}

function slot_block(d, slot, reload)
{
	const [key, label] = slot;
	const entries = d.entries.filter(e => e.slot === key);
	return h("div", { class: "slot" },
		h("div", { class: "slot-head" },
			h("span", {}, label),
			h("button", { type: "button", class: "btn-link",
				      "aria-label": label + " hinzufügen",
				      onclick: () => add_sheet(d.day, key,
							       label, reload) },
			  "+")),
		entries.length ? h("ul", { class: "entries plan-entries" },
				   entries.map(e => entry_line(e, reload)))
			: null);
}

function day_card(d, reload)
{
	const shown = SLOTS.filter(([, , flag]) => !flag || d[flag]);
	const cls = "plan-day" + (d.color ? " mark-" + d.color : "") +
		(d.day === iso(today()) ? " today" : "");
	return h("section", { class: cls },
		h("div", { class: "plan-day-head" },
			h("h2", {}, day_label(d.day)),
			h("button", { type: "button", class: "btn-link",
				      onclick: () => day_sheet(d, reload) },
			  "Tag bearbeiten")),
		d.note ? h("p", { class: "plan-note" }, d.note) : null,
		shown.map(s => slot_block(d, s, reload)));
}

function range_text(r)
{
	return short_date(r.start) + " – " +
		short_date(add_days(r.start, r.days - 1));
}

function view_switch(redraw)
{
	const btn = (v, label) => h("button", {
		type: "button", class: "chip",
		"aria-pressed": String(view === v), onclick: () => {
			view = v;
			offset = 0;
			save_view();
			redraw();
		} }, label);
	return h("div", { class: "chips" }, btn("four", "4 Tage"),
		 btn("week", "Woche"));
}

export async function view_plan()
{
	const box = h("div", { class: "plan-days" });
	const bar = h("div", { class: "plan-nav" });
	const finish = h("a", { class: "btn btn-primary" },
			 "Planung abschliessen");
	const redraw = async () => {
		const r = range();
		const step = (n) => h("button", { type: "button",
			class: "btn-icon", "aria-label": n < 0 ?
			"Zurück" : "Weiter", onclick: () => {
				offset += n;
				redraw();
			} }, n < 0 ? "‹" : "›");
		bar.replaceChildren(step(-1),
			h("span", { class: "plan-range" }, range_text(r)),
			step(1), view_switch(redraw));
		finish.href = "#/plan/shopping?start=" + iso(r.start) +
			"&days=" + r.days;
		try {
			const days = await API.get_plan(iso(r.start), r.days);
			box.replaceChildren(...days.map(d =>
				day_card(d, redraw)));
		} catch (e) {
			toast(error_msg(e), true);
		}
	};
	await redraw();
	return h("div", {},
		topbar("Menüplan"),
		h("main", {}, bar, box,
			h("div", { class: "actions" }, finish)));
}

/* ------------------------------------------------------------------ */
/* Ingredients of the shown days                                       */
/* ------------------------------------------------------------------ */

function hint(i)
{
	if (i.on_list)
		return "schon auf der Liste";
	if (i.freezer)
		return "in der Gefriertruhe";
	return i.pantry ? "Vorrat" : "";
}

function needed(i)
{
	return !i.pantry && !i.on_list && !i.freezer;
}

function ingredient_line(i)
{
	const box = h("input", { type: "checkbox", checked: needed(i) });
	const qty = [fmt_amount(i.amount), i.unit].filter(Boolean).join(" ");
	const extra = [hint(i), i.recipes.join(", ")].filter(Boolean);
	const el = h("li", { class: "item" },
		h("label", { class: "check" }, box,
			h("span", { class: "text" },
				qty ? h("span", { class: "qty" }, qty + " ")
				    : null,
				i.name,
				i.note ? h("span", { class: "note" },
					   ", " + i.note) : null,
				h("span", { class: "note plan-src" },
				  extra.join(" · ")))));
	return { el: el, box: box, item: i };
}

async function to_shopping(lines, btn)
{
	const items = lines.filter(l => l.box.checked).map(l => ({
		name: l.item.name, unit: l.item.unit,
		amount: l.item.amount, note: l.item.note,
	}));
	if (items.length === 0)
		return toast("Nichts ausgewählt", true);
	btn.disabled = true;
	try {
		await API.add_shopping_bulk(items);
		toast(items.length === 1 ? "1 Zutat auf der Einkaufsliste" :
		      items.length + " Zutaten auf der Einkaufsliste", false);
		location.hash = "#/shopping";
	} catch (e) {
		toast(error_msg(e), true);
		btn.disabled = false;
	}
}

export async function view_plan_shopping(query)
{
	const p = new URLSearchParams(query || "");
	const start = p.get("start");
	const days = Number(p.get("days")) || VIEW_DAYS.four;
	const list = await API.plan_ingredients(start, days);
	const sorted = list.filter(needed).concat(
		list.filter(i => !needed(i)));
	const lines = sorted.map(ingredient_line);
	const btn = h("button", { type: "button", class: "btn-primary",
				  onclick: () => to_shopping(lines, btn) },
		      "Auf die Einkaufsliste");
	const range_el = h("p", { class: "meta-line" },
			   range_text({ start: parse_iso(start), days: days }));
	const body = lines.length === 0 ?
		h("p", { class: "empty" }, "Keine Rezepte in diesen Tagen") :
		[h("ul", { class: "shop" }, lines.map(l => l.el)),
		 h("div", { class: "actions" }, btn)];
	return h("div", {},
		topbar("Zutaten", back_button("#/plan")),
		h("main", {}, range_el, body));
}
