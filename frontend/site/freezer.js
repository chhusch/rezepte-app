/*
 * Freezer (#/freezer): what is frozen since when, oldest first.
 * Items older than OLD_DAYS are marked. «Rezepte» opens the list
 * filtered by the item's name, «Raus» takes some or all of it out.
 */

import * as API from "./api.js";
import {
	h, toast, error_msg, topbar, field, fmt_amount, open_sheet,
} from "./form.js";

const OLD_DAYS = 90;
const DAY_MS = 86400000;

function pad2(n)
{
	return String(n).padStart(2, "0");
}

function today_iso()
{
	const d = new Date();
	return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" +
	       pad2(d.getDate());
}

function days_since(s)
{
	const [y, m, d] = s.split("-").map(Number);
	const t = new Date();
	const now = Date.UTC(t.getFullYear(), t.getMonth(), t.getDate());
	return Math.round((now - Date.UTC(y, m - 1, d)) / DAY_MS);
}

function age_text(s)
{
	const n = days_since(s);
	if (n <= 0)
		return "seit heute";
	if (n < 14)
		return n === 1 ? "seit gestern" : "seit " + n + " Tagen";
	if (n < 60)
		return "seit " + Math.floor(n / 7) + " Wochen";
	const m = Math.floor(n / 30);
	return m < 24 ? "seit " + m + " Monaten" :
		"seit " + Math.floor(m / 12) + " Jahren";
}

function fmt_date(s)
{
	const [y, m, d] = s.split("-");
	return d + "." + m + "." + y;
}

function qty_text(i)
{
	return [fmt_amount(i.amount), i.unit].filter(Boolean).join(" ");
}

function to_input(i, amount)
{
	return { name: i.name, amount: amount, unit: i.unit,
		 note: i.note, frozen_on: i.frozen_on };
}

/* ------------------------------------------------------------------ */
/* Sheets                                                              */
/* ------------------------------------------------------------------ */

async function save(fn, close, reload)
{
	try {
		await fn();
		close();
		reload();
	} catch (e) {
		toast(error_msg(e), true);
	}
}

function take_sheet(i, reload)
{
	const all = () => API.delete_freezer(i.id);
	if (i.amount === null) {
		const close = open_sheet("«" + i.name + "» herausnehmen?",
			h("button", { type: "button", class: "btn-primary",
				      onclick: () => save(all, close,
							  reload) },
			  "Herausnehmen"));
		return;
	}
	const n = h("input", { type: "number", min: 0, step: "any",
			       inputmode: "decimal", value: i.amount,
			       "aria-label": "Menge" });
	const some = () => {
		const left = Number(i.amount) - Number(n.value || 0);
		if (left <= 0)
			return all();
		return API.update_freezer(i.id, to_input(i, String(left)));
	};
	const close = open_sheet("Wie viel herausnehmen?",
		h("div", { class: "row" }, n,
		  h("span", { class: "hint" }, i.unit || "Stück")),
		h("button", { type: "button", class: "btn-primary",
			      onclick: () => save(some, close, reload) },
		  "Herausnehmen"),
		h("button", { type: "button",
			      onclick: () => save(all, close, reload) },
		  "Alles herausnehmen"));
	n.select();
}

function item_fields(i)
{
	const f = {
		name: h("input", { value: i.name, required: true,
				   maxlength: 200 }),
		amount: h("input", { type: "number", min: 0, step: "any",
				     inputmode: "decimal",
				     value: i.amount === null ? "" :
					    i.amount }),
		unit: h("input", { value: i.unit, maxlength: 50,
				   placeholder: "g, Stück, Pack" }),
		note: h("input", { value: i.note, maxlength: 200 }),
		date: h("input", { type: "date", value: i.frozen_on }),
	};
	f.read = () => ({
		name: f.name.value, unit: f.unit.value, note: f.note.value,
		amount: f.amount.value === "" ? null : f.amount.value,
		frozen_on: f.date.value || null,
	});
	return f;
}

function edit_sheet(i, reload)
{
	const f = item_fields(i);
	const put = () => API.update_freezer(i.id, f.read());
	const del = () => API.delete_freezer(i.id);
	const close = open_sheet("Bearbeiten",
		field("Name", f.name),
		h("div", { class: "row" }, field("Menge", f.amount),
		  field("Einheit", f.unit)),
		field("Notiz", f.note),
		field("Eingefroren am", f.date),
		h("button", { type: "button", class: "btn-primary",
			      onclick: () => save(put, close, reload) },
		  "Speichern"),
		h("button", { type: "button", class: "btn-danger",
			      onclick: () => save(del, close, reload) },
		  "Löschen"));
}

/* ------------------------------------------------------------------ */
/* List                                                                */
/* ------------------------------------------------------------------ */

function item_line(i, reload)
{
	const old = days_since(i.frozen_on) >= OLD_DAYS;
	const qty = qty_text(i);
	return h("li", { class: "item" + (old ? " old" : "") },
		h("button", { type: "button", class: "text freezer-text",
			      onclick: () => edit_sheet(i, reload) },
			h("span", {},
			  qty ? h("span", { class: "qty" }, qty + " ") : null,
			  i.name,
			  i.note ? h("span", { class: "note" },
				     ", " + i.note) : null),
			h("span", { class: "note freezer-age",
				    title: fmt_date(i.frozen_on) },
			  age_text(i.frozen_on))),
		h("a", { class: "btn-link", href: "#/?zutaten=" +
			 encodeURIComponent(i.name) }, "Rezepte"),
		h("button", { type: "button", class: "btn",
			      onclick: () => take_sheet(i, reload) }, "Raus"));
}

function add_form(reload)
{
	const name = h("input", { placeholder: "Was kommt rein?",
				  "aria-label": "Name", required: true,
				  maxlength: 200, autocomplete: "off" });
	const amount = h("input", { type: "number", min: 0, step: "any",
				    inputmode: "decimal",
				    placeholder: "Menge",
				    "aria-label": "Menge" });
	const unit = h("input", { placeholder: "Einheit",
				  "aria-label": "Einheit", maxlength: 50 });
	const date = h("input", { type: "date", value: today_iso(),
				  "aria-label": "Eingefroren am" });
	return h("form", { class: "shop-add", onsubmit: async (ev) => {
		ev.preventDefault();
		if (name.value.trim() === "")
			return;
		try {
			await API.add_freezer({
				name: name.value, unit: unit.value,
				amount: amount.value === "" ? null :
					amount.value,
				frozen_on: date.value || null,
			});
			name.value = amount.value = unit.value = "";
			date.value = today_iso();
			reload();
		} catch (e) {
			toast(error_msg(e), true);
		}
	} },
		h("div", { class: "row" }, name),
		h("div", { class: "row" }, amount, unit, date),
		h("button", { type: "submit", class: "btn-primary" },
		  "Einfrieren"));
}

export async function view_freezer()
{
	const ul = h("ul", { class: "shop freezer" });
	const reload = async () => {
		try {
			const items = await API.list_freezer();
			ul.replaceChildren(...items.map(i =>
				item_line(i, reload)));
			if (items.length === 0)
				ul.append(h("li", { class: "empty" },
					    "Die Gefriertruhe ist leer"));
		} catch (e) {
			toast(error_msg(e), true);
		}
	};
	await reload();
	return h("div", {},
		topbar("Gefriertruhe"),
		h("main", {}, ul, add_form(reload)));
}
