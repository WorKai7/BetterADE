import json
import re
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar


# ============================================================
# CONFIGURATION
# ============================================================

ICAL_URL = "https://edt.univ-littoral.fr/jsp/custom/modules/plannings/9n9Rr7WP.shu"

ICAL_FILE = Path("planning.shu")
HTML_FILE = Path("docs/index.html")
COLORS_FILE = Path("colors.json")

TIMEZONE = ZoneInfo("Europe/Paris")


# Palette utilisée pour les nouvelles matières
COLORS = [
    "#6366f1",
    "#8b5cf6",
    "#ec4899",
    "#ef4444",
    "#f97316",
    "#eab308",
    "#22c55e",
    "#14b8a6",
    "#06b6d4",
    "#3b82f6",
]


# ============================================================
# TELECHARGEMENT
# ============================================================

def download_ical():
    print("Téléchargement de l'emploi du temps...")

    response = requests.get(ICAL_URL, timeout=30)
    response.raise_for_status()

    ICAL_FILE.write_bytes(response.content)

    print("✓ planning.shu téléchargé")


# ============================================================
# NETTOYAGE
# ============================================================

def clean_course_name(name):
    """
    Supprime les 'a' minuscules placés au début du nom.

    Exemples :
        aaaProgrammation Fonct Av TD/TP
        -> Programmation Fonct Av TD/TP

        aaPython
        -> Python

        Programmation
        -> Programmation
    """

    name = name.strip()

    name = re.sub(r"^a+", "", name)

    return name.strip()


def extract_teacher(description):
    """
    Extrait le professeur depuis DESCRIPTION.

    Exemple :

        \\n\\nGROUPE 1-WebDSci+I2L-Formation initiale
        DEHOS Julien
        (Exporté le:31/08/2026 15:19)

    -> DEHOS Julien
    """

    if not description:
        return ""

    lines = [
        line.strip()
        for line in description.replace("\\n", "\n").splitlines()
        if line.strip()
    ]

    for line in lines:

        # On ignore les lignes contenant les informations de groupe
        if "GROUPE" in line.upper():
            continue

        if "EXPORT" in line.upper():
            continue

        # On évite les lignes trop longues qui sont probablement
        # des informations diverses
        if len(line) > 60:
            continue

        # Un nom de professeur ressemble généralement à :
        # NOM Prénom
        if re.match(r"^[A-ZÀ-ÖØ-Ý][A-ZÀ-ÖØ-Ý' -]+ [A-ZÀ-ÖØ-Ýa-zà-öø-ÿ' -]+$", line):
            return line

    return ""


def extract_group(description):
    """
    Récupère le groupe depuis DESCRIPTION.
    """

    if not description:
        return ""

    match = re.search(
        r"GROUPE\s+(.+?)(?:\n|$)",
        description.replace("\\n", "\n"),
        re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return ""


# ============================================================
# DATES
# ============================================================

def convert_datetime(dt):
    """
    Convertit une date iCalendar en datetime Europe/Paris.
    """

    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime.combine(
            dt,
            datetime.min.time(),
            tzinfo=TIMEZONE
        )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)

    return dt.astimezone(TIMEZONE)


# ============================================================
# PARSING ICAL
# ============================================================

def parse_ical():
    from zoneinfo import ZoneInfo
    
    print("Lecture du calendrier...")

    with open(ICAL_FILE, "rb") as file:
        calendar = Calendar.from_ical(file.read())

    events = []
    
    last_update = calendar.get("DTSTAMP")
    last_modified = None

    for component in calendar.walk("VEVENT"):
        
        modified = component.get("LAST-MODIFIED")
        
        if modified:
            modified = modified.dt

            if last_modified is None or modified > last_modified:
                last_modified = modified
        
        if last_modified:
            last_update = last_modified.astimezone(
                ZoneInfo("Europe/Paris")
            ).strftime("%d/%m/%Y à %H:%M")
        else:
            last_update = "Inconnue"
        
        start = convert_datetime(
            component.get("DTSTART").dt
        )

        end = convert_datetime(
            component.get("DTEND").dt
        )

        raw_name = str(
            component.get("SUMMARY", "")
        )

        name = clean_course_name(raw_name)

        description = str(
            component.get("DESCRIPTION", "")
        )

        location = str(
            component.get("LOCATION", "")
        ).strip()

        teacher = extract_teacher(description)

        group = extract_group(description)

        events.append({
            "id": str(component.get("UID", "")),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "name": name,
            "location": location,
            "teacher": teacher,
            "group": group,
            "description": description,
        })

    events.sort(
        key=lambda event: event["start"]
    )

    print(f"✓ {len(events)} cours trouvés")

    return events, last_update


# ============================================================
# COULEURS
# ============================================================

def load_colors():

    if COLORS_FILE.exists():

        try:
            return json.loads(
                COLORS_FILE.read_text(
                    encoding="utf-8"
                )
            )

        except json.JSONDecodeError:
            print("⚠ colors.json invalide, recréation")


    return {}


def save_colors(colors):

    COLORS_FILE.write_text(
        json.dumps(
            colors,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )


def assign_colors(events):

    colors = load_colors()

    color_index = len(colors)

    for event in events:

        name = event["name"]

        if name not in colors:

            colors[name] = COLORS[
                color_index % len(COLORS)
            ]

            color_index += 1

    save_colors(colors)

    print(
        f"✓ {len(colors)} matières dans colors.json"
    )

    return colors


# ============================================================
# GENERATION HTML
# ============================================================

def generate_html(events, colors, last_update):

    events_json = json.dumps(
        events,
        ensure_ascii=False
    )

    colors_json = json.dumps(
        colors,
        ensure_ascii=False
    )

    html = f"""<!DOCTYPE html>
    <html lang="fr">

    <head>

    <meta charset="UTF-8">

    <meta name="viewport"
        content="width=device-width, initial-scale=1.0">

    <title>Mon emploi du temps</title>

    <style>

    * {{
        box-sizing: border-box;
    }}

    :root {{

        --background: #f4f5f7;
        --surface: #ffffff;
        --surface-hover: #f1f3f5;

        --text: #111827;
        --text-secondary: #6b7280;

        --border: #e5e7eb;

        --header-height: 70px;
        --hour-height: 70px;
    }}

    [data-theme="dark"] {{

        --background: #0f1117;
        --surface: #171a23;
        --surface-hover: #202431;

        --text: #f3f4f6;
        --text-secondary: #9ca3af;

        --border: #292e3a;
    }}

    body {{

        margin: 0;

        background: var(--background);
        color: var(--text);

        font-family:
            Inter,
            system-ui,
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;

        transition:
            background .2s,
            color .2s;
    }}


    /* ============================================================
    HEADER
    ============================================================ */

    header {{

        height: var(--header-height);

        display: flex;
        align-items: center;

        justify-content: space-between;

        padding: 0 24px;

        background: var(--surface);

        border-bottom:
            1px solid var(--border);

        position: sticky;
        top: 0;

        z-index: 100;
    }}

    .title {{

        font-size: 20px;
        font-weight: 700;

        white-space: nowrap;
    }}

    .controls {{

        display: flex;
        align-items: center;

        gap: 8px;
    }}

    button {{

        border: none;

        border-radius: 9px;

        padding: 9px 13px;

        background:
            var(--surface-hover);

        color: var(--text);

        cursor: pointer;

        font-size: 14px;

        transition:
            transform .1s,
            background .15s;
    }}

    button:hover {{
        transform: translateY(-1px);
    }}

    button:active {{
        transform: translateY(0);
    }}

    .icon-button {{

        width: 40px;
        height: 40px;

        padding: 0;

        font-size: 18px;
    }}

    .today-button {{
        font-weight: 600;
    }}

    .period {{

        min-width: 230px;

        text-align: center;

        font-weight: 600;

        color: var(--text);
    }}


    /* ============================================================
    CALENDAR
    ============================================================ */

    .calendar-container {{

        padding: 20px;

        max-width: 1800px;

        margin: auto;
    }}

    .calendar {{

        display: grid;

        grid-template-columns:
            65px repeat(7, minmax(120px, 1fr));

        background: var(--surface);

        border:
            1px solid var(--border);

        border-radius: 14px;

        overflow: hidden;
    }}


    /* ============================================================
    DAY HEADERS
    ============================================================ */

    .day-header {{

        height: 60px;

        display: flex;

        flex-direction: column;

        align-items: center;

        justify-content: center;

        border-bottom:
            1px solid var(--border);

        border-left:
            1px solid var(--border);

        font-size: 12px;

        color: var(--text-secondary);
    }}

    .day-header strong {{

        font-size: 14px;

        color: var(--text);
    }}

    .day-header.today strong {{

        color: #6366f1;
    }}


    /* ============================================================
    HOURS
    ============================================================ */

    .hours {{

        position: relative;

        border-right:
            1px solid var(--border);
    }}

    .hour {{

        height: var(--hour-height);

        display: flex;

        justify-content: center;

        padding-top: 5px;

        font-size: 11px;

        color: var(--text-secondary);
    }}


    /* ============================================================
    DAY
    ============================================================ */

    .day {{

        position: relative;

        height:
            calc(
                (20 - 8) *
                var(--hour-height)
            );

        border-left:
            1px solid var(--border);

    }}

    .hour-line {{

        position: absolute;

        left: 0;
        right: 0;

        height: 1px;

        background: var(--border);

        opacity: .7;
    }}


    /* ============================================================
    EVENTS
    ============================================================ */

    .event {{

        position: absolute;

        left: 5px;
        right: 5px;

        border-radius: 9px;

        padding: 8px 9px;

        color: white;

        overflow: hidden;

        cursor: pointer;

        box-shadow:
            0 2px 6px rgba(0,0,0,.15);

        transition:
            transform .12s,
            filter .12s;

        z-index: 2;
    }}

    .event:hover {{

        transform:
            scale(1.015);

        filter:
            brightness(1.08);

        z-index: 5;
    }}

    .event-title {{

        font-weight: 700;

        font-size: 12px;

        line-height: 1.3;

    }}

    .event-time {{

        margin-top: 4px;

        font-size: 11px;

        opacity: .85;
    }}

    .event-location {{

        margin-top: 3px;

        font-size: 11px;

        opacity: .9;
    }}

    .event-teacher {{

        margin-top: 3px;

        font-size: 11px;

        opacity: .9;
    }}


    /* ============================================================
    MODAL
    ============================================================ */

    .modal-backdrop {{

        position: fixed;

        inset: 0;

        background:
            rgba(0,0,0,.5);

        display: none;

        align-items: center;

        justify-content: center;

        z-index: 1000;

        padding: 20px;
    }}

    .modal-backdrop.visible {{
        display: flex;
    }}

    .modal {{

        width: min(500px, 100%);

        background: var(--surface);

        border-radius: 16px;

        padding: 24px;

        box-shadow:
            0 20px 60px rgba(0,0,0,.3);
    }}

    .modal h2 {{

        margin-top: 0;

        margin-bottom: 20px;

    }}

    .detail {{

        padding: 10px 0;

        border-bottom:
            1px solid var(--border);

    }}

    .detail:last-child {{
        border-bottom: none;
    }}

    .detail-label {{

        font-size: 11px;

        color:
            var(--text-secondary);

        margin-bottom: 3px;
    }}

    .detail-value {{
        font-weight: 500;
    }}


    /* ============================================================
    MOBILE
    ============================================================ */

    @media (max-width: 700px) {{

        header {{

            height: auto;

            min-height: 65px;

            padding: 10px 12px;

            gap: 10px;

        }}

        .title {{
            display: none;
        }}

        .period {{

            min-width: 0;

            flex: 1;

            font-size: 14px;
        }}

        .calendar-container {{
            padding: 10px;
        }}

        .calendar {{

            grid-template-columns:
                50px 1fr;

            border-radius: 10px;

        }}

        .day-header {{

            height: 55px;

        }}

        .event {{
            left: 4px;
            right: 4px;
        }}

        .event-title {{
            font-size: 13px;
        }}

        .event-location,
        .event-teacher {{
            font-size: 12px;
        }}

    }}


    /* ============================================================
    VERY SMALL SCREENS
    ============================================================ */

    @media (max-width: 430px) {{

        .controls {{
            gap: 4px;
        }}

        button {{
            padding: 8px 9px;
        }}

        .icon-button {{
            width: 36px;
            height: 36px;
        }}

    }}

    </style>

    </head>


    <body>

    <header>

        <div class="title">
            📅 Emploi du temps
        </div>
        
        <div class="last-update">
            Dernière mise à jour de l'EDT : {last_update}
        </div>

        <div class="controls">

            <button
                class="icon-button"
                onclick="previousDay()">
                ‹
            </button>

            <div
                class="period"
                id="period">
            </div>

            <button
                class="icon-button"
                onclick="nextDay()">
                ›
            </button>

            <button
                class="today-button"
                onclick="goToday()">
                Aujourd'hui
            </button>

            <button
                class="icon-button"
                onclick="toggleTheme()"
                id="themeButton">
                🌙
            </button>

        </div>

    </header>


    <div class="calendar-container">

        <div id="calendar"></div>

    </div>


    <div
        class="modal-backdrop"
        id="modalBackdrop"
        onclick="closeModal(event)"
    >

        <div
            class="modal"
            onclick="event.stopPropagation()"
        >

            <h2 id="modalTitle"></h2>

            <div id="modalContent"></div>

        </div>

    </div>


    <script>


    // ============================================================
    // DATA
    // ============================================================

    const events = {events_json};

    const colors = {colors_json};


    // ============================================================
    // STATE
    // ============================================================

    let currentDate = new Date();

    const START_HOUR = 8;
    const END_HOUR = 20;

    const HOUR_HEIGHT = 70;


    // ============================================================
    // DATE HELPERS
    // ============================================================

    function sameDay(a, b) {{

        return (
            a.getFullYear() === b.getFullYear() &&
            a.getMonth() === b.getMonth() &&
            a.getDate() === b.getDate()
        );

    }}


    function startOfWeek(date) {{

        const d = new Date(date);

        const day = d.getDay();

        const diff =
            day === 0
                ? -6
                : 1 - day;

        d.setDate(
            d.getDate() + diff
        );

        d.setHours(0, 0, 0, 0);

        return d;
    }}


    function formatTime(date) {{

        return date.toLocaleTimeString(
            "fr-FR",
            {{
                hour: "2-digit",
                minute: "2-digit"
            }}
        );

    }}


    // ============================================================
    // VIEW
    // ============================================================

    function render() {{

        const calendar =
            document.getElementById("calendar");

        calendar.innerHTML = "";

        /*
        * Sur téléphone :
        * affichage du jour uniquement.
        *
        * Sur ordinateur :
        * affichage de la semaine.
        */

        if (window.innerWidth <= 700) {{
            renderDay(calendar);
        }} else {{
            renderWeek(calendar);
        }}

    }}


    // ============================================================
    // WEEK VIEW
    // ============================================================

    function renderWeek(calendar) {{

        const monday =
            startOfWeek(currentDate);

        const days = [];

        for (let i = 0; i < 7; i++) {{

            const d =
                new Date(monday);

            d.setDate(
                monday.getDate() + i
            );

            days.push(d);

        }}


        document.getElementById(
            "period"
        ).textContent =
            days[0].toLocaleDateString(
                "fr-FR",
                {{
                    day: "numeric",
                    month: "long"
                }}
            )
            +
            " → "
            +
            days[6].toLocaleDateString(
                "fr-FR",
                {{
                    day: "numeric",
                    month: "long",
                    year: "numeric"
                }}
            );


        calendar.className =
            "calendar";


        calendar.style.gridTemplateColumns =
            "65px repeat(7, minmax(120px, 1fr))";


        // Coin supérieur gauche
        calendar.appendChild(
            document.createElement("div")
        );


        // Jours
        days.forEach(day => {{

            const header =
                document.createElement("div");

            header.className =
                "day-header";

            if (
                sameDay(
                    day,
                    new Date()
                )
            ) {{
                header.classList.add("today");
            }}

            header.innerHTML = `
                <strong>
                    ${{day.toLocaleDateString(
                        "fr-FR",
                        {{ weekday: "long" }}
                    )}}
                </strong>

                ${{day.getDate()}}/
                ${{day.getMonth() + 1}}
            `;

            calendar.appendChild(header);

        }});


        // Colonne des heures
        calendar.appendChild(
            createHours()
        );


        // Colonnes des jours
        days.forEach(day => {{

            const column =
                createDayColumn(day);

            calendar.appendChild(
                column
            );

        }});

    }}


    // ============================================================
    // DAY VIEW
    // ============================================================

    function renderDay(calendar) {{

        document.getElementById(
            "period"
        ).textContent =
            currentDate.toLocaleDateString(
                "fr-FR",
                {{
                    weekday: "long",
                    day: "numeric",
                    month: "long",
                    year: "numeric"
                }}
            );


        calendar.className =
            "calendar";

        calendar.style.gridTemplateColumns =
            "50px 1fr";


        calendar.appendChild(
            document.createElement("div")
        );


        const header =
            document.createElement("div");

        header.className =
            "day-header";


        header.innerHTML = `
            <strong>
                ${{currentDate.toLocaleDateString(
                    "fr-FR",
                    {{ weekday: "long" }}
                )}}
            </strong>

            ${{currentDate.getDate()}}/
            ${{currentDate.getMonth() + 1}}
        `;


        calendar.appendChild(header);


        calendar.appendChild(
            createHours()
        );


        calendar.appendChild(
            createDayColumn(currentDate)
        );

    }}


    // ============================================================
    // HOURS
    // ============================================================

    function createHours() {{

        const hours =
            document.createElement("div");

        hours.className =
            "hours";


        hours.style.height =
            `${{
                (END_HOUR - START_HOUR)
                * HOUR_HEIGHT
            }}px`;


        for (
            let h = START_HOUR;
            h < END_HOUR;
            h++
        ) {{

            const hour =
                document.createElement("div");

            hour.className =
                "hour";

            hour.textContent =
                `${{
                    String(h).padStart(2, "0")
                }}:00`;

            hours.appendChild(hour);

        }}


        return hours;

    }}


    // ============================================================
    // DAY COLUMN
    // ============================================================

    function createDayColumn(day) {{

        const column =
            document.createElement("div");

        column.className =
            "day";


        for (
            let h = START_HOUR;
            h <= END_HOUR;
            h++
        ) {{

            const line =
                document.createElement("div");

            line.className =
                "hour-line";

            line.style.top =
                `${{
                    (h - START_HOUR)
                    * HOUR_HEIGHT
                }}px`;

            column.appendChild(line);

        }}


        events
            .filter(event =>
                sameDay(
                    new Date(event.start),
                    day
                )
            )
            .forEach(event =>
                addEvent(
                    column,
                    event
                )
            );


        return column;

    }}


    // ============================================================
    // EVENT
    // ============================================================

    function addEvent(column, event) {{

        const start = new Date(event.start);
        const end = new Date(event.end);

        const startMinutes =
            start.getHours() * 60 + start.getMinutes();

        const endMinutes =
            end.getHours() * 60 + end.getMinutes();

        const top =
            (
                startMinutes - START_HOUR * 60
            ) / 60 * HOUR_HEIGHT;

        const height =
            (
                endMinutes - startMinutes
            ) / 60 * HOUR_HEIGHT;

        const element = document.createElement("div");

        element.className = "event";

        element.style.top = `${{top}}px`;

        element.style.height =
            `${{Math.max(height - 4, 25)}}px`;

        element.style.background =
            colors[event.name] || "#6366f1";

        element.innerHTML = `

            <div class="event-title">
                ${{escapeHtml(event.name)}}
            </div>

            <div class="event-time">
                ${{formatTime(start)}} – ${{formatTime(end)}}
            </div>

            ${{event.location
                ? `
                    <div class="event-location">
                        📍 ${{escapeHtml(event.location)}}
                    </div>
                `
                : ""
            }}

            ${{event.teacher
                ? `
                    <div class="event-teacher">
                        👨‍🏫 ${{escapeHtml(event.teacher)}}
                    </div>
                `
                : ""
            }}

        `;

        element.onclick = () => openModal(event);

        column.appendChild(element);
    }}


    // ============================================================
    // MODAL
    // ============================================================

    function openModal(event) {{

        document.getElementById("modalTitle").textContent =
            event.name;

        const start = new Date(event.start);
        const end = new Date(event.end);

        document.getElementById("modalContent").innerHTML = `

            <div class="detail">

                <div class="detail-label">
                    Horaire
                </div>

                <div class="detail-value">
                    ${{start.toLocaleDateString("fr-FR")}}
                    <br>
                    ${{formatTime(start)}} – ${{formatTime(end)}}
                </div>

            </div>

            ${{event.teacher
                ? `
                    <div class="detail">

                        <div class="detail-label">
                            Professeur
                        </div>

                        <div class="detail-value">
                            👨‍🏫 ${{escapeHtml(event.teacher)}}
                        </div>

                    </div>
                `
                : ""
            }}

            ${{event.location
                ? `
                    <div class="detail">

                        <div class="detail-label">
                            Salle
                        </div>

                        <div class="detail-value">
                            📍 ${{escapeHtml(event.location)}}
                        </div>

                    </div>
                `
                : ""
            }}

            ${{event.group
                ? `
                    <div class="detail">

                        <div class="detail-label">
                            Groupe
                        </div>

                        <div class="detail-value">
                            ${{escapeHtml(event.group)}}
                        </div>

                    </div>
                `
                : ""
            }}

        `;

        document.getElementById(
            "modalBackdrop"
        ).classList.add("visible");
    }}


    function closeModal(event) {{

        if (event.target.id === "modalBackdrop") {{

            document.getElementById(
                "modalBackdrop"
            ).classList.remove("visible");

        }}

    }}


    // ============================================================
    // NAVIGATION
    // ============================================================

    function previousDay() {{

        if (window.innerWidth <= 700) {{

            currentDate.setDate(
                currentDate.getDate() - 1
            );

        }} else {{

            currentDate.setDate(
                currentDate.getDate() - 7
            );

        }}

        render();

    }}


    function nextDay() {{

        if (window.innerWidth <= 700) {{

            currentDate.setDate(
                currentDate.getDate() + 1
            );

        }} else {{

            currentDate.setDate(
                currentDate.getDate() + 7
            );

        }}

        render();

    }}


    function goToday() {{

        currentDate =
            new Date();

        render();

    }}


    // ============================================================
    // THEME
    // ============================================================

    function toggleTheme() {{

        const html =
            document.documentElement;

        const current =
            html.dataset.theme;

        const newTheme =
            current === "dark"
                ? "light"
                : "dark";


        html.dataset.theme =
            newTheme;


        localStorage.setItem(
            "theme",
            newTheme
        );


        document.getElementById(
            "themeButton"
        ).textContent =
            newTheme === "dark"
                ? "☀️"
                : "🌙";

    }}


    function loadTheme() {{

        const saved =
            localStorage.getItem(
                "theme"
            );


        if (saved) {{

            document.documentElement
                .dataset.theme =
                saved;

        }} else if (
            window.matchMedia(
                "(prefers-color-scheme: dark)"
            ).matches
        ) {{

            document.documentElement
                .dataset.theme =
                "dark";

        }}


        document.getElementById(
            "themeButton"
        ).textContent =
            document.documentElement
                .dataset.theme === "dark"
                ? "☀️"
                : "🌙";

    }}


    // ============================================================
    // UTILS
    // ============================================================

    function escapeHtml(text) {{

        const div =
            document.createElement("div");

        div.textContent =
            text;

        return div.innerHTML;

    }}


    // ============================================================
    // RESPONSIVE
    // ============================================================

    window.addEventListener(
        "resize",
        render
    );


    // ============================================================
    // START
    // ============================================================

    loadTheme();

    render();

    </script>

    </body>

    </html>
    """

    HTML_FILE.write_text(
        html,
        encoding="utf-8"
    )

print("✓ index.html généré")


# ============================================================
# MAIN
# ============================================================

def main():

    download_ical()

    events, last_update = parse_ical()

    colors = assign_colors(events)

    generate_html(
        events,
        colors,
        last_update
    )

    print()
    print("✓ Terminé !")
    print(f"  → {HTML_FILE}")
    print(f"  → {COLORS_FILE}")


if __name__ == "__main__":
    main()
