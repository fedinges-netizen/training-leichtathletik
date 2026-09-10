import calendar
import json
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st


DATA_FILE = Path(__file__).with_name("trainingseinheiten.json")
USERS_FILE = Path(__file__).with_name("accounts.json")
ROLES = ["Athlet", "Trainer"]
DISCIPLINES = [
	"Sprint",
	"Mittelstrecke",
	"Langstrecke",
	"Sprung",
	"Wurf",
	"Krafttraining",
	"Regeneration",
	"Wettkampf",
	"Sonstiges",
]
INTENSITIES = ["Locker", "Moderat", "Hart", "Maximal"]

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
				label = f"**{day_number}**"
				if selected_day == date.today():
					label += " · heute"
				st.markdown(label)
				if not day_sessions:
					st.caption("-")
					continue
				for session in day_sessions:
					st.markdown(
						f"`{session['discipline']}`  \n"
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
			role = st.selectbox("Rolle", ROLES)
			register_submitted = st.form_submit_button("Account erstellen", type="primary")
		if register_submitted:
			clean_name = name.strip()
			if not clean_name:
				st.error("Bitte gib deinen Namen ein.")
			elif any(user["name"].casefold() == clean_name.casefold() for user in users):
				st.error("Dieser Name ist bereits registriert.")
			else:
				new_user = create_user(clean_name, role)
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

users = load_users()
sessions = load_sessions()

st.session_state.setdefault("current_user_id", None)
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
	else [session for session in sessions if session.get("user_id") == current_user["id"]]
)

st.title("TrackLog")
st.caption("Dein Trainingstagebuch für Leichtathletik")


@st.dialog("Neue Trainingseinheit")
def new_session_dialog():
	st.write("Trage hier alle Daten deiner Trainingseinheit ein.")
	with st.form("new_session", clear_on_submit=True):
		session_date = st.date_input("Datum", today, format="DD.MM.YYYY")
		title = st.text_input("Bezeichnung", placeholder="z. B. 6 × 200 m")
		discipline = st.selectbox("Disziplin", DISCIPLINES)
		intensity = st.select_slider("Intensität", options=INTENSITIES, value="Moderat")
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


if st.button("+ Neue Trainingseinheit", type="primary"):
	new_session_dialog()


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

with list_col:
	st.subheader("Letzte Einheiten")
	if not visible_sessions:
		st.info("Noch keine Einheiten gespeichert. Nutze das Formular links, um zu starten.")
	else:
		recent = sorted(visible_sessions, key=lambda session: session["date"], reverse=True)[:10]
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
				for trainer_note in session.get("trainer_notes", []):
					st.info(
						f"Trainernotiz von {trainer_note.get('trainer_name', 'Trainer')}: "
						f"{trainer_note.get('note', '')}"
					)

st.divider()
st.subheader("Alle Einheiten")
if visible_sessions:
	table = pd.DataFrame(visible_sessions).sort_values("date", ascending=False)
	table["Datum"] = pd.to_datetime(table["date"]).dt.strftime("%d.%m.%Y")
	table["Dauer"] = table["duration"].map(format_duration)
	table["Distanz"] = table["distance"].map(lambda value: f"{value:.1f} km" if value else "-")
	table["Trainernotizen"] = table.get("trainer_notes", pd.Series(index=table.index)).map(format_trainer_notes)
	columns = ["Datum", "title", "discipline", "Dauer", "Distanz", "intensity", "notes", "Trainernotizen"]
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
			"Eigene Einheit löschen",
			options=[session["id"] for session in visible_sessions],
			format_func=lambda item_id: next(
				f"{session['date']} · {session['title']}"
				for session in visible_sessions
				if session["id"] == item_id
			),
		)
		if st.button("Ausgewählte Einheit löschen"):
			save_sessions([session for session in sessions if session["id"] != delete_id])
			st.rerun()
