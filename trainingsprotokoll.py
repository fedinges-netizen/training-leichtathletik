import calendar
import json
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st


DATA_FILE = Path(__file__).with_name("trainingseinheiten.json")
USERS_FILE = Path(__file__).with_name("accounts.json")
DEFAULT_TRAINER_ID = "default-trainer-account"
ROLES = ["Athlet"]
DISCIPLINES = [
	"Dauerlauf",
	"Tempodauerlauf",
	"Schwelle",
	"VO2max",
	"Berganläufe",
	"WKA 1500",
	"WKA 800",
	"SKA",
	"Sprints",
	"Kraft",
	"SK nerval",
]
INTENSITIES = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]

MONTHS = [
	"Januar", "Februar", "März", "April", "Mai", "Juni",
	"Juli", "August", "September", "Oktober", "November", "Dezember",
]


def load_sessions():
	if not DATA_FILE.exists():
		return []
	try:
		with DATA_FILE.open("r", encoding="utf-8") as file:
			sessions = json.load(file)
		return sessions if isinstance(sessions, list) else []
	except (OSError, json.JSONDecodeError):
		return []


def save_sessions(sessions):
	with DATA_FILE.open("w", encoding="utf-8") as file:
		json.dump(sessions, file, ensure_ascii=False, indent=2)


def load_users():
	if not USERS_FILE.exists():
		return []
	try:
		with USERS_FILE.open("r", encoding="utf-8") as file:
			users = json.load(file)
		return users if isinstance(users, list) else []
	except (OSError, json.JSONDecodeError):
		return []


def save_users(users):
	with USERS_FILE.open("w", encoding="utf-8") as file:
		json.dump(users, file, ensure_ascii=False, indent=2)


def ensure_default_trainer(users):
	athletes = [user for user in users if user.get("role") != "Trainer"]
	default_trainer = {
		"id": DEFAULT_TRAINER_ID,
		"name": "Trainer",
		"role": "Trainer",
	}
	updated_users = athletes + [default_trainer]
	if updated_users != users:
		save_users(updated_users)
	return updated_users


def user_label(user):
	return f"{user['name']} ({user['role']})"


def create_user(name, role):
	return {"id": str(uuid4()), "name": name.strip(), "role": role}


def format_duration(minutes):
	hours, remaining = divmod(int(minutes), 60)
	return f"{hours} h {remaining:02d} min" if hours else f"{remaining} min"


def sessions_for_day(sessions, selected_day):
	return [session for session in sessions if session["date"] == selected_day.isoformat()]


def render_calendar(sessions, year, month):
	st.subheader(f"{MONTHS[month - 1]} {year}")
	month_grid = calendar.monthcalendar(year, month)
	weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
	header = st.columns(7)
	for column, weekday in zip(header, weekdays):
		column.markdown(f"**{weekday}**")

	for week in month_grid:
		columns = st.columns(7)
		for column, day_number in zip(columns, week):
			with column:
				if not day_number:
					st.write("")
					continue
				selected_day = date(year, month, day_number)
				day_sessions = sessions_for_day(sessions, selected_day)
				day_label = str(day_number)
				if selected_day == date.today():
					day_label += " · heute"
				if st.button(
					day_label,
					key=f"calendar_day_{selected_day.isoformat()}",
					width="stretch",
				):
					st.session_state.calendar_selected_date = selected_day.isoformat()
					st.session_state.calendar_dialog_open = True
				if not day_sessions:
					st.caption("Keine Einheit")
					continue
				if selected_day != date.today():
					st.caption(f"{len(day_sessions)} Einheit(en) · Tag öffnen für Details")
					continue
				for session in day_sessions:
					assignment_label = "Vorgabe · " if session.get("is_assignment") else ""
					if session.get("is_assignment_result"):
						assignment_label = "Ergebnis · "
					if session.get("is_assignment") and session.get("results", {}).get(
						st.session_state.get("current_user_id", "")
					):
						assignment_label = "Vorgabe · Ergebnisse eingetragen · "
					st.markdown(
						f"`{assignment_label}{session['discipline']}`  \n"
						f"{session['title']}  \n"
						f"{format_duration(session['duration'])} · {session['intensity']}"
					)


def add_session(sessions, values, user):
	sessions.append(
		{
			"id": str(uuid4()),
			"user_id": user["id"],
			"athlete_name": user["name"],
			"date": values["date"].isoformat(),
			"title": values["title"].strip(),
			"discipline": values["discipline"],
			"duration": values["duration"],
			"distance": values["distance"],
			"intensity": values["intensity"],
			"notes": values["notes"].strip(),
			"created_at": datetime.now().isoformat(timespec="seconds"),
		}
	)
	save_sessions(sessions)


def add_assignment(sessions, values, trainer, athlete_ids):
	sessions.append(
		{
			"id": str(uuid4()),
			"user_id": trainer["id"],
			"athlete_name": trainer["name"],
			"date": values["date"].isoformat(),
			"title": values["title"].strip(),
			"discipline": values["discipline"],
			"duration": values["duration"],
			"distance": values["distance"],
			"intensity": values["intensity"],
			"notes": values["notes"].strip(),
			"is_assignment": True,
			"assigned_athlete_ids": athlete_ids,
			"results": {},
			"created_at": datetime.now().isoformat(timespec="seconds"),
		}
	)
	save_sessions(sessions)


def update_assignment(sessions, assignment_id, values, athlete_ids):
	for session in sessions:
		if session["id"] == assignment_id and session.get("is_assignment"):
			session.update(
				{
					"date": values["date"].isoformat(),
					"title": values["title"].strip(),
					"discipline": values["discipline"],
					"duration": values["duration"],
					"distance": values["distance"],
					"intensity": values["intensity"],
					"notes": values["notes"].strip(),
					"assigned_athlete_ids": athlete_ids,
				}
			)
			break
	save_sessions(sessions)


def delete_assignment(sessions, assignment_id, trainer_id):
	assignment = next(
		(
			session for session in sessions
			if session["id"] == assignment_id
			and session.get("is_assignment")
			and session.get("user_id") == trainer_id
		),
		None,
	)
	if assignment is None:
		return False
	sessions[:] = [
		session for session in sessions
		if session["id"] != assignment_id and session.get("assignment_id") != assignment_id
	]
	save_sessions(sessions)
	return True


def save_assignment_result(sessions, session_id, athlete, values):
	assignment = next(session for session in sessions if session["id"] == session_id)
	result = {
		"athlete_name": athlete["name"],
		"duration": values["duration"],
		"distance": values["distance"],
		"intensity": values["intensity"],
		"notes": values["notes"].strip(),
		"completed_at": datetime.now().isoformat(timespec="seconds"),
	}
	assignment.setdefault("results", {})[athlete["id"]] = result

	result_session = next(
		(
			session for session in sessions
			if session.get("is_assignment_result")
			and session.get("assignment_id") == session_id
			and session.get("user_id") == athlete["id"]
		),
		None,
	)
	result_values = {
		"date": assignment["date"],
		"title": f"Ergebnis: {assignment['title']}",
		"discipline": assignment["discipline"],
		"duration": result["duration"],
		"distance": result["distance"],
		"intensity": result["intensity"],
		"notes": result["notes"],
	}
	if result_session is None:
		sessions.append(
			{
				"id": str(uuid4()),
				"user_id": athlete["id"],
				"athlete_name": athlete["name"],
				"assignment_id": session_id,
				"is_assignment_result": True,
				"created_at": result["completed_at"],
				"date": assignment["date"],
				"title": result_values["title"],
				"discipline": result_values["discipline"],
				"duration": result_values["duration"],
				"distance": result_values["distance"],
				"intensity": result_values["intensity"],
				"notes": result_values["notes"],
			}
		)
	else:
		result_session.update(result_values)
	save_sessions(sessions)


def update_session(sessions, session_id, values):
	for session in sessions:
		if session["id"] == session_id:
			session.update(
				{
					"date": values["date"].isoformat(),
					"title": values["title"].strip(),
					"discipline": values["discipline"],
					"duration": values["duration"],
					"distance": values["distance"],
					"intensity": values["intensity"],
					"notes": values["notes"].strip(),
				}
			)
			break
	save_sessions(sessions)


def add_trainer_note(sessions, session_id, note, trainer):
	for session in sessions:
		if session["id"] == session_id:
			session.setdefault("trainer_notes", []).append(
				{
					"trainer_id": trainer["id"],
					"trainer_name": trainer["name"],
					"note": note.strip(),
					"created_at": datetime.now().isoformat(timespec="seconds"),
				}
			)
			break
	save_sessions(sessions)


def format_trainer_notes(notes):
	if not isinstance(notes, list) or not notes:
		return "-"
	return "\n".join(
		f"{entry.get('trainer_name', 'Trainer')}: {entry.get('note', '')}"
		for entry in notes
		if isinstance(entry, dict)
	) if notes else "-"


def render_authentication(users):
	st.title("TrackLog")
	st.caption("Trainingstagebuch für Leichtathletik")
	st.subheader("Willkommen")
	st.write("Melde dich an oder erstelle einen neuen Account, um deine Trainingseinheiten zu verwalten.")

	login_tab, register_tab = st.tabs(["Anmelden", "Neuen Account erstellen"])
	with login_tab:
		if not users:
			st.info("Es gibt noch keine Accounts. Erstelle zuerst einen neuen Account.")
		else:
			with st.form("login_form"):
				selected_id = st.selectbox(
					"Account auswählen",
					options=[user["id"] for user in users],
					format_func=lambda user_id: next(
						user_label(user) for user in users if user["id"] == user_id
					),
				)
				login_submitted = st.form_submit_button("Anmelden", type="primary")
			if login_submitted:
				return next(user for user in users if user["id"] == selected_id)

	with register_tab:
		with st.form("register_form", clear_on_submit=True):
			name = st.text_input("Name", placeholder="z. B. Anna Müller")
			st.caption("Neue Accounts werden als Athleten angelegt. Der Trainer-Account ist bereits vorgegeben.")
			register_submitted = st.form_submit_button("Account erstellen", type="primary")
		if register_submitted:
			clean_name = name.strip()
			if not clean_name:
				st.error("Bitte gib deinen Namen ein.")
			elif any(user["name"].casefold() == clean_name.casefold() for user in users):
				st.error("Dieser Name ist bereits registriert.")
			else:
				new_user = create_user(clean_name, "Athlet")
				save_users(users + [new_user])
				st.success("Account erstellt. Du wirst angemeldet.")
				return new_user

	return None


st.set_page_config(page_title="TrackLog", page_icon="🏃", layout="wide")
st.markdown(
	"""
	<style>
	.block-container { max-width: 1400px; padding-top: 2rem; }
	[data-testid="stMetric"] { background: #f2f4f1; border-left: 4px solid #d95d39; padding: 0.7rem; }
	[data-testid="stColumn"] { min-height: 90px; }
	</style>
	""",
	unsafe_allow_html=True,
)

users = ensure_default_trainer(load_users())
sessions = load_sessions()

st.session_state.setdefault("current_user_id", None)
st.session_state.setdefault("calendar_selected_date", None)
st.session_state.setdefault("calendar_dialog_open", False)
current_user = next(
	(user for user in users if user["id"] == st.session_state.current_user_id),
	None,
)
if current_user is None:
	new_user = render_authentication(users)
	if new_user is not None:
		st.session_state.current_user_id = new_user["id"]
		st.rerun()
	st.stop()

today = date.today()
visible_sessions = (
	sessions
	if current_user["role"] == "Trainer"
	else [
		session for session in sessions
		if session.get("user_id") == current_user["id"]
		or current_user["id"] in session.get("assigned_athlete_ids", [])
	]
)
today_sessions = sessions_for_day(visible_sessions, date.today())

st.title("TrackLog")
st.caption("Dein Trainingstagebuch für Leichtathletik")


@st.dialog("Neue Trainingseinheit")
def new_session_dialog():
	st.write("Trage hier alle Daten deiner Trainingseinheit ein.")
	with st.form("new_session", clear_on_submit=True):
		session_date = st.date_input("Datum", today, format="DD.MM.YYYY")
		title = st.text_input("Bezeichnung", placeholder="z. B. 6 × 200 m")
		discipline = st.selectbox("Disziplin", DISCIPLINES)
		intensity = st.select_slider("Intensität", options=INTENSITIES, value=INTENSITIES[0])
		duration = st.number_input("Dauer in Minuten", min_value=1, max_value=600, value=60, step=5)
		distance = st.number_input("Distanz in km", min_value=0.0, max_value=200.0, value=0.0, step=0.1)
		notes = st.text_area("Notizen", placeholder="Gefühl, Zeiten, Wiederholungen ...")
		submitted = st.form_submit_button("Einheit speichern", type="primary", width="stretch")

	if submitted:
		if not title.strip():
			st.error("Bitte gib der Einheit eine Bezeichnung.")
		else:
			add_session(
				sessions,
				{
					"date": session_date,
					"title": title,
					"discipline": discipline,
					"duration": duration,
					"distance": distance,
					"intensity": intensity,
					"notes": notes,
				},
				current_user,
			)
			st.success("Training gespeichert.")
			st.rerun()


def render_assignment_form(default_date=None, form_key="assignment_form"):
	athletes = [user for user in users if user["role"] == "Athlet"]
	if not athletes:
		st.info("Es gibt noch keine Athleten-Accounts.")
		return

	with st.form(form_key, clear_on_submit=True):
		if default_date is None:
			assignment_date = st.date_input("Datum", today, format="DD.MM.YYYY")
		else:
			assignment_date = default_date
			st.write(f"Datum: {default_date.strftime('%d.%m.%Y')}")
		title = st.text_input("Bezeichnung", placeholder="z. B. 5 × 1.000 m")
		selected_athletes = st.multiselect(
			"Athleten auswählen",
			options=[athlete["id"] for athlete in athletes],
			format_func=lambda athlete_id: next(
				athlete["name"] for athlete in athletes if athlete["id"] == athlete_id
			),
		)
		discipline = st.selectbox("Disziplin", DISCIPLINES)
		intensity = st.select_slider("Intensität", options=INTENSITIES, value=INTENSITIES[0])
		duration = st.number_input("Vorgesehene Dauer in Minuten", min_value=1, max_value=600, value=60, step=5)
		distance = st.number_input("Vorgesehene Distanz in km", min_value=0.0, max_value=200.0, value=0.0, step=0.1)
		notes = st.text_area("Anweisungen", placeholder="Serien, Pausen, Tempo oder weitere Hinweise ...")
		created = st.form_submit_button("Vorgabe veröffentlichen", type="primary", width="stretch")

	if created:
		if not title.strip():
			st.error("Bitte gib der Vorgabe eine Bezeichnung.")
		elif not selected_athletes:
			st.error("Bitte wähle mindestens einen Athleten aus.")
		else:
			add_assignment(
				sessions,
				{
					"date": assignment_date,
					"title": title,
					"discipline": discipline,
					"intensity": intensity,
					"duration": duration,
					"distance": distance,
					"notes": notes,
				},
				current_user,
				selected_athletes,
			)
			st.success("Vorgabe veröffentlicht.")
			st.rerun()


@st.dialog("Trainingsvorgabe erstellen")
def assignment_dialog():
	render_assignment_form()


def render_assignment_edit_form(assignment, selected_day):
	athletes = [user for user in users if user["role"] == "Athlet"]
	with st.form(f"edit_assignment_{assignment['id']}"):
		title = st.text_input("Bezeichnung", value=assignment.get("title", ""))
		selected_athletes = st.multiselect(
			"Athleten auswählen",
			options=[athlete["id"] for athlete in athletes],
			default=[
				athlete_id for athlete_id in assignment.get("assigned_athlete_ids", [])
				if athlete_id in {athlete["id"] for athlete in athletes}
			],
			format_func=lambda athlete_id: next(
				athlete["name"] for athlete in athletes if athlete["id"] == athlete_id
			),
		)
		discipline = st.selectbox(
			"Disziplin",
			DISCIPLINES,
			index=DISCIPLINES.index(assignment["discipline"])
			if assignment.get("discipline") in DISCIPLINES else 0,
		)
		intensity = st.select_slider(
			"Intensität",
			options=INTENSITIES,
			value=assignment.get("intensity") if assignment.get("intensity") in INTENSITIES else INTENSITIES[0],
		)
		duration = st.number_input(
			"Vorgesehene Dauer in Minuten",
			min_value=1,
			max_value=600,
			value=int(assignment.get("duration", 60)),
			step=5,
		)
		distance = st.number_input(
			"Vorgesehene Distanz in km",
			min_value=0.0,
			max_value=200.0,
			value=float(assignment.get("distance", 0.0)),
			step=0.1,
		)
		notes = st.text_area("Anweisungen", value=assignment.get("notes", ""))
		updated = st.form_submit_button("Vorgabe speichern", type="primary", width="stretch")

	if updated:
		if not title.strip():
			st.error("Bitte gib der Vorgabe eine Bezeichnung.")
		elif not selected_athletes:
			st.error("Bitte wähle mindestens einen Athleten aus.")
		else:
			update_assignment(
				sessions,
				assignment["id"],
				{
					"date": selected_day,
					"title": title,
					"discipline": discipline,
					"intensity": intensity,
					"duration": duration,
					"distance": distance,
					"notes": notes,
				},
				selected_athletes,
			)
			st.success("Vorgabe geändert.")
			st.rerun()


@st.dialog("Trainingseinheit für diesen Tag")
def calendar_session_dialog(selected_day):
	day_sessions = sessions_for_day(visible_sessions, selected_day)
	st.write(f"{selected_day.strftime('%d.%m.%Y')}")
	if current_user["role"] == "Trainer":
		assignment_sessions = [session for session in day_sessions if session.get("is_assignment")]
		if day_sessions:
			st.subheader("Vorhandene Einheiten")
			for session in day_sessions:
				entry_type = "Vorgabe" if session.get("is_assignment") else "Trainingseinheit"
				st.caption(
					f"{entry_type}: {session['title']} · {session['discipline']} · "
					f"{format_duration(session['duration'])}"
				)
		if assignment_sessions:
			assignment_mode = st.radio(
				"Vorgabe auswählen",
				["Neue Vorgabe erstellen", "Bestehende Vorgabe bearbeiten"],
				key=f"trainer_assignment_mode_{selected_day.isoformat()}",
			)
			if assignment_mode == "Bestehende Vorgabe bearbeiten":
				selected_assignment_id = st.selectbox(
					"Vorgabe",
					options=[session["id"] for session in assignment_sessions],
					format_func=lambda session_id: next(
						session["title"] for session in assignment_sessions if session["id"] == session_id
					),
					key=f"trainer_assignment_{selected_day.isoformat()}",
				)
				selected_assignment = next(
					session for session in assignment_sessions if session["id"] == selected_assignment_id
				)
				render_assignment_edit_form(selected_assignment, selected_day)
				if st.button("Vorgabe löschen", key=f"delete_assignment_{selected_day.isoformat()}"):
					if delete_assignment(sessions, selected_assignment_id, current_user["id"]):
						st.session_state.calendar_dialog_open = False
						st.rerun()
			else:
				render_assignment_form(selected_day, form_key=f"calendar_assignment_{selected_day.isoformat()}")
		else:
			render_assignment_form(selected_day, form_key=f"calendar_assignment_{selected_day.isoformat()}")
		return
	assignment_sessions = [session for session in day_sessions if session.get("is_assignment")]
	editable_sessions = [
		session for session in day_sessions
		if not session.get("is_assignment") and not session.get("is_assignment_result")
	]
	if current_user["role"] == "Athlet" and assignment_sessions:
		available_modes = ["Trainingsergebnisse eintragen", "Neue Einheit hinzufügen"]
		if editable_sessions:
			available_modes.append("Bestehende Einheit bearbeiten")
		mode = st.radio(
			"Was möchtest du tun?",
			available_modes,
			key=f"calendar_mode_{selected_day.isoformat()}",
		)
		if mode == "Trainingsergebnisse eintragen":
			selected_id = st.selectbox(
				"Vorgabe auswählen",
				options=[session["id"] for session in assignment_sessions],
				format_func=lambda session_id: next(
					session["title"] for session in assignment_sessions if session["id"] == session_id
				),
				key=f"assignment_session_{selected_day.isoformat()}",
			)
			assignment = next(session for session in assignment_sessions if session["id"] == selected_id)
			st.info(
				f"Vorgabe: {assignment['title']} · {assignment['discipline']} · "
				f"{format_duration(assignment['duration'])}"
			)
			if assignment.get("notes"):
				st.write(f"Anweisungen: {assignment['notes']}")
			result = assignment.get("results", {}).get(current_user["id"], {})
			with st.form(f"assignment_result_{selected_id}"):
				st.subheader("Deine Trainingsergebnisse")
				result_duration = st.number_input(
					"Tatsächliche Dauer in Minuten",
					min_value=1,
					max_value=600,
					value=int(result.get("duration", assignment.get("duration", 60))),
					step=5,
				)
				result_distance = st.number_input(
					"Tatsächliche Distanz in km",
					min_value=0.0,
					max_value=200.0,
					value=float(result.get("distance", assignment.get("distance", 0.0))),
					step=0.1,
				)
				result_intensity = st.select_slider(
					"Tatsächliche Intensität",
					options=INTENSITIES,
					value=result.get("intensity", assignment.get("intensity", INTENSITIES[0])),
				)
				result_notes = st.text_area("Ergebnisse und Notizen", value=result.get("notes", ""))
				result_submitted = st.form_submit_button("Ergebnisse speichern", type="primary", width="stretch")
			if result_submitted:
				save_assignment_result(
					sessions,
					selected_id,
					current_user,
					{
						"duration": result_duration,
						"distance": result_distance,
						"intensity": result_intensity,
						"notes": result_notes,
					},
				)
				st.success("Deine Ergebnisse wurden gespeichert.")
				st.session_state.calendar_dialog_open = False
				st.rerun()
			return
	else:
		mode = None

	if day_sessions:
		available_modes = ["Neue Einheit hinzufügen", "Bestehende Einheit bearbeiten"]
		if mode is None:
			mode = st.radio(
				"Was möchtest du tun?",
				available_modes,
				key=f"calendar_mode_{selected_day.isoformat()}",
			)
	else:
		mode = "Neue Einheit hinzufügen"
		st.info("An diesem Tag gibt es noch keine Einheit. Lege jetzt eine neue an.")

	if mode == "Bestehende Einheit bearbeiten":
		editable_sessions = editable_sessions or day_sessions
		selected_id = st.selectbox(
			"Einheit auswählen",
			options=[session["id"] for session in editable_sessions],
			format_func=lambda session_id: next(
				session["title"] for session in editable_sessions if session["id"] == session_id
			),
			key=f"calendar_session_{selected_day.isoformat()}",
		)
		selected_session = next(session for session in editable_sessions if session["id"] == selected_id)
		with st.form(f"edit_session_{selected_id}"):
			title = st.text_input("Bezeichnung", value=selected_session.get("title", ""))
			discipline = st.selectbox(
				"Disziplin",
				DISCIPLINES,
				index=DISCIPLINES.index(selected_session["discipline"])
				if selected_session.get("discipline") in DISCIPLINES else 0,
			)
			intensity = st.select_slider(
				"Intensität",
				options=INTENSITIES,
				value=selected_session["intensity"] if selected_session.get("intensity") in INTENSITIES else INTENSITIES[0],
			)
			duration = st.number_input("Dauer in Minuten", min_value=1, max_value=600, value=int(selected_session.get("duration", 60)), step=5)
			distance = st.number_input("Distanz in km", min_value=0.0, max_value=200.0, value=float(selected_session.get("distance", 0.0)), step=0.1)
			notes = st.text_area("Notizen", value=selected_session.get("notes", ""))
			updated = st.form_submit_button("Änderungen speichern", type="primary", width="stretch")
		if updated:
			if not title.strip():
				st.error("Bitte gib der Einheit eine Bezeichnung.")
			else:
				update_session(
					sessions,
					selected_id,
					{
						"date": selected_day,
						"title": title,
						"discipline": discipline,
						"intensity": intensity,
						"duration": duration,
						"distance": distance,
						"notes": notes,
					},
				)
				st.success("Einheit geändert.")
				st.session_state.calendar_dialog_open = False
				st.rerun()
	else:
		with st.form(f"new_session_for_{selected_day.isoformat()}", clear_on_submit=True):
			title = st.text_input("Bezeichnung", placeholder="z. B. 6 × 200 m")
			discipline = st.selectbox("Disziplin", DISCIPLINES)
			intensity = st.select_slider("Intensität", options=INTENSITIES, value=INTENSITIES[0])
			duration = st.number_input("Dauer in Minuten", min_value=1, max_value=600, value=60, step=5)
			distance = st.number_input("Distanz in km", min_value=0.0, max_value=200.0, value=0.0, step=0.1)
			notes = st.text_area("Notizen", placeholder="Gefühl, Zeiten, Wiederholungen ...")
			created = st.form_submit_button("Einheit speichern", type="primary", width="stretch")
		if created:
			if not title.strip():
				st.error("Bitte gib der Einheit eine Bezeichnung.")
			else:
				add_session(
					sessions,
					{
						"date": selected_day,
						"title": title,
						"discipline": discipline,
						"intensity": intensity,
						"duration": duration,
						"distance": distance,
						"notes": notes,
					},
					current_user,
				)
				st.success("Training gespeichert.")
				st.session_state.calendar_dialog_open = False
				st.rerun()


if current_user["role"] != "Trainer" and st.button("+ Neue Trainingseinheit", type="primary"):
	new_session_dialog()
if current_user["role"] == "Trainer" and st.button("+ Trainingsvorgabe erstellen"):
	assignment_dialog()


with st.sidebar:
	st.header("TrackLog")
	st.caption(f"Angemeldet als: {current_user['name']} ({current_user['role']})")
	if st.button("Abmelden"):
		st.session_state.current_user_id = None
		st.rerun()
	st.divider()
	st.caption(f"Gespeichert in `{DATA_FILE.name}`")

st.header("Übersicht")
total_minutes = sum(session["duration"] for session in visible_sessions)
total_distance = sum(session["distance"] for session in visible_sessions)
current_month = [session for session in visible_sessions if session["date"].startswith(today.strftime("%Y-%m"))]
metrics = st.columns(4)
metrics[0].metric("Einheiten gesamt", len(visible_sessions))
metrics[1].metric("Diesen Monat", len(current_month))
metrics[2].metric("Trainingszeit", format_duration(total_minutes))
metrics[3].metric("Kilometer", f"{total_distance:.1f} km")

calendar_col, list_col = st.columns([1.45, 1])
with calendar_col:
	selected_month = st.date_input("Kalendermonat auswählen", today.replace(day=1), format="DD.MM.YYYY")
	render_calendar(visible_sessions, selected_month.year, selected_month.month)
	if st.session_state.calendar_dialog_open and st.session_state.calendar_selected_date:
		calendar_session_dialog(date.fromisoformat(st.session_state.calendar_selected_date))

with list_col:
	st.subheader("Heute")
	if not today_sessions:
		st.info("Für heute sind keine Einheiten eingetragen.")
	else:
		recent = sorted(today_sessions, key=lambda session: session["date"], reverse=True)
		for session in recent:
			with st.container(border=True):
				st.markdown(f"**{session['title']}** · {session['discipline']}")
				if current_user["role"] == "Trainer":
					st.caption(f"Athlet: {session.get('athlete_name', 'Unbekannt')}")
				st.caption(
					f"{datetime.fromisoformat(session['date']).strftime('%d.%m.%Y')} · "
					f"{format_duration(session['duration'])} · {session['intensity']}"
				)
				if session["distance"]:
					st.write(f"Distanz: {session['distance']:.1f} km")
				if session["notes"]:
					st.caption(session["notes"])
				if session.get("is_assignment") and current_user["role"] == "Athlet":
					result = session.get("results", {}).get(current_user["id"])
					if result:
						st.success(
							f"Ergebnisse eingetragen: {format_duration(result['duration'])} · "
							f"{result['distance']:.1f} km"
						)
				for trainer_note in session.get("trainer_notes", []):
					st.info(
						f"Trainernotiz von {trainer_note.get('trainer_name', 'Trainer')}: "
						f"{trainer_note.get('note', '')}"
					)

st.divider()
st.subheader("Einheiten von heute")
if today_sessions:
	table = pd.DataFrame(today_sessions).sort_values("date", ascending=False)
	table["Datum"] = pd.to_datetime(table["date"]).dt.strftime("%d.%m.%Y")
	table["Dauer"] = table["duration"].map(format_duration)
	table["Distanz"] = table["distance"].map(lambda value: f"{value:.1f} km" if value else "-")
	table["Trainernotizen"] = table.get("trainer_notes", pd.Series(index=table.index)).map(format_trainer_notes)
	table["Art"] = table.apply(
		lambda row: "Vorgabe" if row.get("is_assignment") else "Ergebnis" if row.get("is_assignment_result") else "Training",
		axis=1,
	)
	columns = ["Datum", "Art", "title", "discipline", "Dauer", "Distanz", "intensity", "notes", "Trainernotizen"]
	if current_user["role"] == "Trainer":
		table["Athlet"] = table.get("athlete_name", pd.Series(index=table.index)).fillna("Unbekannt")
		columns.insert(1, "Athlet")
	st.dataframe(
		table[columns].rename(
			columns={
				"title": "Einheit",
				"discipline": "Disziplin",
				"intensity": "Intensität",
				"notes": "Notizen",
			}
		),
		hide_index=True,
		width="stretch",
	)

	if current_user["role"] == "Trainer":
		st.subheader("Trainernotiz hinterlassen")
		with st.form("trainer_note_form", clear_on_submit=True):
			selected_session_id = st.selectbox(
				"Trainingseinheit auswählen",
				options=[session["id"] for session in visible_sessions],
				format_func=lambda session_id: next(
					f"{session['date']} · {session.get('athlete_name', 'Unbekannt')} · {session['title']}"
					for session in visible_sessions
					if session["id"] == session_id
				),
			)
			note = st.text_area("Notiz für den Athleten", placeholder="Feedback, Hinweise oder Empfehlungen ...")
			note_submitted = st.form_submit_button("Notiz speichern", type="primary", width="stretch")
		if note_submitted:
			if not note.strip():
				st.error("Bitte gib eine Notiz ein.")
			else:
				add_trainer_note(sessions, selected_session_id, note, current_user)
				st.success("Trainernotiz gespeichert.")
				st.rerun()

	if current_user["role"] == "Athlet":
		delete_id = st.selectbox(
			"Eigene Einheit von heute löschen",
			options=[session["id"] for session in today_sessions],
			format_func=lambda item_id: next(
				f"{session['date']} · {session['title']}"
				for session in today_sessions
				if session["id"] == item_id
			),
		)
		if st.button("Ausgewählte Einheit löschen"):
			save_sessions([session for session in sessions if session["id"] != delete_id])
			st.rerun()
