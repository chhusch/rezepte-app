/*
 * Account (#/konto): household members, own color, invites, password,
 * log out on every device. on_logout tells app.js the session is
 * gone. The invite page (#/einladung/TOKEN) is view_invite in app.js.
 */

import * as API from "./api.js";
import {
	h, append, toast, error_msg, field, topbar, fmt_date, copy_link,
	send_link,
} from "./form.js";

/* Like replaceChildren, but skips null like h() does. */
function refill(el, ...children)
{
	el.replaceChildren();
	append(el, children);
}

export const MIN_PASSWORD_LEN = 12;
export const INVITE_HASH = "#/einladung/";

const COLORS = [
	["sea", "Grün"], ["razz", "Pink"], ["mustard", "Senf"],
	["coffee", "Kaffee"],
];

function password_input(autocomplete)
{
	return h("input", { type: "password", autocomplete: autocomplete,
			    required: true });
}

function member_dot(color)
{
	return h("span", { class: "member-dot by-" + color });
}

/* ---- household ---- */

async function remove(u, reload)
{
	if (!confirm(u.username + " entfernen? Notizen bleiben."))
		return;
	try {
		await API.remove_user(u.id);
		reload();
	} catch (e) {
		toast(error_msg(e), true);
	}
}

function user_row(u, reload)
{
	const del = u.me ? h("span", { class: "muted" }, "du") :
		h("button", { type: "button", class: "btn-link",
			      onclick: () => remove(u, reload) },
		  "Entfernen");
	return h("li", {}, member_dot(u.color), h("span", {}, u.username), del);
}

function color_picker(me, reload)
{
	const pick = async (c) => {
		try {
			await API.set_color(c);
			reload(false);
		} catch (e) {
			toast(error_msg(e), true);
		}
	};
	return h("div", { class: "colors", role: "group",
			  "aria-label": "Meine Farbe" },
		COLORS.map(([c, label]) => h("button", {
			type: "button", class: "color-btn by-" + c,
			"aria-label": label, title: label,
			"aria-pressed": String(c === me.color),
			onclick: () => pick(c) })));
}

function invite_url(token)
{
	return location.origin + "/" + INVITE_HASH + token;
}

async function new_invite(box, reload)
{
	try {
		const inv = await API.create_invite();
		const url = invite_url(inv.token);
		refill(box,
			h("p", {}, "Einmal gültig, bis " +
			  fmt_date(inv.expires_at) + ":"),
			h("input", { value: url, readonly: true,
				     "aria-label": "Einladungslink",
				     onfocus: (ev) => ev.target.select() }),
			h("div", { class: "actions" },
				h("button", { type: "button",
					      onclick: () => copy_link(url) },
				  "Kopieren"),
				navigator.share ? h("button", {
					type: "button",
					onclick: () => send_link(url) },
				  "Teilen") : null));
		reload(false);
	} catch (e) {
		toast(error_msg(e), true);
	}
}

function invite_row(inv, reload)
{
	return h("li", {},
		h("span", {}, "Offen bis " + fmt_date(inv.expires_at)),
		h("button", { type: "button", class: "btn-link",
			      onclick: async () => {
			await API.delete_invite(inv.id);
			reload();
		} }, "Zurückziehen"));
}

async function household_section()
{
	const sec = h("section", {});
	const box = h("div", { class: "invite-box" });
	const reload = async (clear = true) => {
		const [users, invites] = await Promise.all([
			API.list_users(), API.list_invites()]);
		const me = users.find(u => u.me);
		if (clear)
			refill(box,);
		refill(sec,
			h("h2", {}, "Haushalt"),
			h("ul", { class: "members" },
			  users.map(u => user_row(u, reload))),
			h("p", { class: "label" }, "Meine Farbe"),
			color_picker(me, reload),
			h("p", { class: "label" }, "Einladungen"),
			invites.length ? h("ul", { class: "members" },
				invites.map(i => invite_row(i, reload)))
				: null,
			h("div", { class: "actions" },
				h("button", { type: "button",
					      onclick: () =>
						new_invite(box, reload) },
				  "Einladen")),
			box);
	};
	await reload();
	return sec;
}

/* ---- password and sessions ---- */

function password_form()
{
	const cur = password_input("current-password");
	const pass = password_input("new-password");
	pass.minLength = MIN_PASSWORD_LEN;
	const again = password_input("new-password");
	const btn = h("button", { type: "submit", class: "btn-primary" },
		      "Passwort ändern");
	const form = h("form", { onsubmit: async (ev) => {
		ev.preventDefault();
		if (pass.value !== again.value) {
			toast("Passwörter stimmen nicht überein", true);
			return;
		}
		btn.disabled = true;
		try {
			await API.change_password(cur.value, pass.value);
			form.reset();
			toast("Passwort geändert, andere Geräte abgemeldet");
		} catch (e) {
			toast(error_msg(e), true);
		}
		btn.disabled = false;
	} },
		h("h2", {}, "Passwort ändern"),
		field("Aktuelles Passwort", cur),
		field("Neues Passwort (mind. " + MIN_PASSWORD_LEN +
		      " Zeichen)", pass),
		field("Neues Passwort wiederholen", again),
		h("div", { class: "actions" }, btn));
	return h("section", {}, form);
}

function logout_all_block(on_logout)
{
	const btn = h("button", { type: "button", onclick: async () => {
		btn.disabled = true;
		try {
			await API.logout_all();
			on_logout();
		} catch (e) {
			toast(error_msg(e), true);
			btn.disabled = false;
		}
	} }, "Überall abmelden");
	return h("section", {},
		h("h2", {}, "Geräte"),
		h("p", {}, "Meldet alle Geräte ab, auch dieses."),
		h("div", { class: "actions" }, btn));
}

export async function view_account(on_logout)
{
	return h("div", {},
		topbar("Konto"),
		h("main", { class: "account" },
			await household_section(),
			password_form(),
			logout_all_block(on_logout)));
}
