/*
 * Account (#/konto): change the password, log out on every device.
 * Both end all other sessions; on_logout tells app.js the session
 * is gone.
 */

import * as API from "./api.js";
import { h, toast, error_msg, field, topbar } from "./form.js";

export const MIN_PASSWORD_LEN = 12;

function password_input(autocomplete)
{
	return h("input", { type: "password", autocomplete: autocomplete,
			    required: true });
}

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
	return form;
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

export function view_account(on_logout)
{
	return h("div", {},
		topbar("Konto"),
		h("main", { class: "account" },
			password_form(),
			logout_all_block(on_logout)));
}
