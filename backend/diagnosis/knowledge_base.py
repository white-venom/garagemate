"""
Symptom knowledge base.

This is the "traditional logic" part of the bot. Each issue type has:
  - keywords used to figure out what the customer is talking about
  - follow-up questions (asked one at a time, with quick reply options)
  - possible causes, each with signal words that make it more or less likely
  - the service we'd recommend and a default severity
  - what to look up on the web for this kind of problem (news, recalls, known issues)

Questions are asked in order, but each one can decide if it's relevant:
  - skip_if:         don't ask if the customer already said one of these
  - only_if:         only ask if the conversation so far mentions one of these
  - skip_when_known: don't ask if the conversation already has this vehicle field (e.g. fuel_type)
Both skip_if and only_if look at the description AND the answers given so far, so the
questions follow the customer's answers ("drives normally" -> no "when is it worst?").

Keyword syntax: "brak*" matches any word starting with "brak", anything else
matches whole words/phrases. Numbers are weights. See core/text.py.

Wrote these from common workshop experience + owner manuals, it's not exhaustive
but covers the stuff people usually complain about.
"""

from dataclasses import dataclass, field

LOW, MEDIUM, HIGH, CRITICAL = "low", "medium", "high", "critical"
SEVERITY_ORDER = [LOW, MEDIUM, HIGH, CRITICAL]


@dataclass(frozen=True)
class Question:
    key: str
    text: str
    options: tuple = ()
    # don't ask if the customer already mentioned one of these
    skip_if: tuple = ()
    # only ask if something in the conversation points this way
    only_if: tuple = ()
    # don't ask if the conversation already knows this (e.g. "fuel_type")
    skip_when_known: str = ""


@dataclass(frozen=True)
class Cause:
    name: str
    signals: dict
    prior: float = 0.5  # how common this is before we know anything
    severity: str = ""  # overrides the issue severity when this is the top cause
    # only possible on these fuels (glow plugs are diesel only), empty = any car
    fuels: tuple = ()


SPARK_IGNITION = ("petrol", "cng", "lpg", "hybrid")


@dataclass(frozen=True)
class IssueType:
    key: str
    label: str
    intro: str
    keywords: dict
    questions: tuple
    causes: tuple
    service_code: str
    severity: str
    advice: str
    escalations: dict = field(default_factory=dict)  # pattern -> severity
    # what to search the web for (news, recalls, known issues), see diagnosis/research.py
    research_focus: str = ""
    # True: research as soon as the fuel type is known and share it during the questions
    # (mileage). False: research once at diagnosis time, only if we know the car model.
    research_early: bool = False


VEHICLE_QUESTION = Question(
    key="vehicle",
    text="Which car is it? Make, model and year, and roughly how many km it has done (e.g. \"2018 Swift, 60,000 km\").",
    options=("I'd rather not say",),
)

FUEL_WORDS = ("petrol", "diesel", "cng", "electric", "ev", "hybrid", "lpg")

FUEL_QUESTION = Question(
    "fuel",
    "Which fuel does it run on?",
    ("Petrol", "Diesel", "CNG", "Petrol + CNG", "Electric", "Hybrid"),
    skip_if=FUEL_WORDS,
    skip_when_known="fuel_type",
)

ONSET_QUESTION = Question(
    "onset",
    "When did you first notice it?",
    ("Today / suddenly", "In the last few days", "Gradually over weeks", "Right after a service or repair"),
    # they already said when: "since last week", "2 days ago", "after the service"...
    skip_if=(
        "since", "yesterday", "today", "this morning", "last week", "last month", "few days", "couple of days",
        "for weeks", "for months", "after service", "after the service",
        "after servicing", "suddenly", "gradually", "all of a sudden",
    ),
)

# engine: warning light path vs "it drives badly" path
LIGHT_WORDS = (
    "check engine", "engine light", "warning light*", "light is on", "light on", "light came on", "light stays",
    "light remains", "engine symbol", "yes steady", "yes blinking",
)
DRIVE_WORDS = (
    "less power", "poor pickup", "pickup", "power loss", "loss of power", "lack of power", "rough idl*", "shak*",
    "jerk*", "stall*", "misfir*", "hesitat*", "sputter*", "vibrat*",
)


ISSUE_TYPES = [
    IssueType(
        key="brakes",
        label="Brakes",
        intro="Brake problems are worth taking seriously, let's narrow it down.",
        keywords={"brak*": 4, "abs": 4, "stopping distance": 3, "squeal*": 1, "squeak*": 1, "caliper*": 3, "disc pad*": 3},
        questions=(
            Question(
                "noise",
                "Do you hear any noise when you brake?",
                ("Squealing / squeaking", "Grinding / metal sound", "No noise"),
                skip_if=("squeal*", "squeak*", "grind*", "screech*"),
            ),
            Question(
                "pedal",
                "How does the brake pedal feel?",
                ("Soft / goes down too far", "Vibrates or pulses", "Very hard to press", "Feels normal"),
                skip_if=("spongy", "soft pedal", "pedal goes down", "vibrat*", "puls*"),
            ),
            Question(
                "behaviour",
                "Does the car pull to one side while braking, or is the brake/ABS warning light on?",
                ("Pulls to one side", "ABS or brake light is on", "Both", "Neither"),
                skip_if=("pull*", "abs light", "brake light"),
            ),
            Question(
                "pads_age",
                "When were the brake pads last changed?",
                ("Within the last year", "1 to 2 years ago", "More than 2 years ago / never", "Not sure"),
            ),
            ONSET_QUESTION,
        ),
        causes=(
            Cause("Worn brake pads", {"squeal*": 3, "squeak*": 3, "screech*": 2, "more than 2 years": 2, "never": 1}, prior=1.0),
            Cause(
                "Pads worn down to metal, damaging the discs",
                {"grind*": 4, "metal*": 2, "scrap*": 2, "more than 2 years": 1},
                prior=0.5,
                severity=HIGH,
            ),
            Cause("Warped brake discs (rotors)", {"vibrat*": 3, "puls*": 3, "shudder*": 3, "steering shak*": 2}, prior=0.6),
            Cause(
                "Low brake fluid, air in the lines or a fluid leak",
                {"soft": 3, "spongy": 3, "goes down": 3, "sink*": 2, "leak*": 2, "brake light": 2},
                prior=0.4,
                severity=CRITICAL,
            ),
            Cause("Sticking brake caliper", {"pull*": 3, "one side": 3, "burning smell": 2, "hot wheel": 2}, prior=0.4),
            Cause("Brake booster / vacuum problem", {"hard to press": 4, "stiff": 2, "hard pedal": 3}, prior=0.2, severity=HIGH),
            Cause("Faulty ABS sensor or wiring", {"abs": 3}, prior=0.3),
            Cause("Pads or discs not bedded in after the recent brake job", {"right after a service": 3, "within the last year": 1}, prior=0.15, severity=LOW),
        ),
        service_code="brake-service",
        severity=MEDIUM,
        advice="Keep extra distance from the car in front and avoid hard braking until the brakes are inspected.",
        escalations={"grind*": HIGH, "brake failure": CRITICAL, "no brakes": CRITICAL, "brakes failed": CRITICAL},
        research_focus="brake related recalls, service campaigns or common brake complaints for this model",
    ),
    IssueType(
        key="starting",
        label="Starting & battery",
        intro="Starting problems are usually battery related, but not always. A few quick checks:",
        keywords={
            "wont start": 5, "doesnt start": 5, "not starting": 5, "cant start": 5, "no start": 4, "fails to start": 5,
            "not start*": 4, "when starting": 3, "start*": 1, "crank*": 3, "battery": 3, "jump start*": 4, "self": 2, "ignition": 2,
            "dead": 1, "click*": 1,
        },
        questions=(
            Question(
                "crank",
                "What happens when you turn the key or press the start button?",
                ("Nothing at all", "Just clicking", "Cranks slowly", "Cranks normally but doesn't start"),
                skip_if=("click*", "tick*", "tik", "crank*", "slow*", "nothing happens"),
            ),
            Question(
                "lights",
                "Do the dashboard lights and headlights come on normally?",
                ("Bright and normal", "Dim or flickering", "Completely dead"),
                skip_if=("dim*", "flicker*"),
            ),
            Question(
                "before",
                "Did anything happen before this?",
                ("Car stood unused for days", "Lights or music were left on", "It was jump started recently", "Nothing like that"),
            ),
            Question(
                "battery_age",
                "How old is the battery, roughly?",
                ("Under 2 years", "2 to 4 years", "Older than 4 years", "Not sure"),
                skip_if=("new battery", "old battery", "year* old", "months old"),
            ),
            Question(
                "fuel_level",
                "It cranks but doesn't fire, so let's rule out fuel. How much is in the tank?",
                ("Almost empty", "Enough fuel", "Fuel gauge isn't working"),
                only_if=("cranks normally", "cranks but", "turns over"),
            ),
            Question(
                "fuel",
                "Which fuel does it run on?",
                FUEL_QUESTION.options,
                skip_if=FUEL_WORDS,
                only_if=("cranks normally", "cranks but", "turns over"),
                skip_when_known="fuel_type",
            ),
        ),
        causes=(
            Cause(
                "Weak or discharged battery",
                {"click*": 3, "slow*": 3, "dim*": 3, "flicker*": 2, "older than 4": 3, "old battery": 3,
                 "morning*": 2, "cold": 1, "jump start*": 3, "completely dead": 2, "stood unused": 3, "left on": 3},
                prior=1.2,
            ),
            Cause("Loose or corroded battery terminals", {"corro*": 4, "loose": 2, "white powder": 4, "flicker*": 1}, prior=0.5),
            Cause("Faulty starter motor or solenoid", {"single click": 3, "nothing at all": 2, "bright and normal": 2, "self": 1}, prior=0.5),
            Cause(
                "Fuel delivery problem (fuel pump, filter or empty tank)",
                {"cranks normally": 4, "almost empty": 4, "gauge isnt working": 2, "fuel": 1},
                prior=0.4,
            ),
            Cause(
                "Glow plugs (diesel cold start)",
                {"diesel": 2, "cranks normally": 1, "cold": 2, "morning*": 1},
                prior=0.15,
                fuels=("diesel",),
            ),
            Cause(
                "Alternator not charging the battery",
                {"battery light": 4, "keeps dying": 3, "drain*": 2, "new battery": 2, "under 2 years": 1, "jump started recently": 2},
                prior=0.4,
            ),
            Cause("Immobiliser or key fob issue", {"immobili*": 5, "security light": 4, "key fob": 3, "spare key": 2}, prior=0.15),
        ),
        service_code="battery-electrical",
        severity=MEDIUM,
        advice="Don't keep cranking for more than 10 seconds at a time, it drains the battery further and heats the starter.",
        research_focus="known starting, battery or immobiliser problems and recalls for this model",
    ),
    IssueType(
        key="engine",
        label="Engine & check engine light",
        intro="Okay, let's work out what the engine is telling us.",
        keywords={
            "check engine": 5, "engine light": 5, "misfir*": 5, "rough idl*": 5, "idl*": 2, "stall*": 3,
            "power loss": 4, "loss of power": 4, "lack of power": 4, "no power": 3, "pickup": 3, "accelerat*": 2,
            "hesitat*": 3, "knock*": 2, "sputter*": 3, "engine": 1, "rpm": 2, "jerk*": 1,
        },
        questions=(
            Question(
                "light_present",
                "Is the check engine light (the orange engine-shaped symbol) on?",
                ("Yes, steady", "Yes, blinking", "No warning light"),
                skip_if=LIGHT_WORDS,
            ),
            Question(
                "light_state",
                "Is the engine light steady, or does it blink?",
                ("Steady, stays on all the time", "Blinking / flashing", "Comes and goes"),
                skip_if=("blink*", "flash*", "steady", "solid", "stays on", "all the time", "remains on", "comes and goes"),
                only_if=LIGHT_WORDS,
            ),
            Question(
                "drivability",
                "Does the car drive any differently since this started?",
                ("Drives normally", "Less power / poor pickup", "Rough idle or shaking", "Jerks or stalls"),
                skip_if=DRIVE_WORDS,
            ),
            Question(
                "when_worst",
                "When is it worst?",
                ("At idle / standing still", "While accelerating", "When the engine is cold", "All the time"),
                only_if=DRIVE_WORDS,
            ),
            Question(
                "other_lights",
                "Is any other warning light on along with it?",
                ("Battery light", "Oil pressure light", "Temperature light", "No other lights"),
                only_if=LIGHT_WORDS,
            ),
            Question(
                "history",
                "Did it start right after refuelling or a service?",
                ("Right after refuelling", "Right after a service or repair", "Neither"),
                skip_if=("after refuel*", "after service", "after the service"),
            ),
            FUEL_QUESTION,
        ),
        causes=(
            Cause(
                "Loose fuel cap or a small leak in the fuel vapour (EVAP) system",
                {
                    "refuel*": 4, "petrol fill*": 4, "fuel fill*": 4, "fill* petrol": 4, "fill* fuel": 4, "fill* up": 3,
                    "full tank": 3, "tank full": 3, "petrol pump": 2,
                    "fuel cap": 5, "tank cap": 5, "drives normally": 2, "drives fine": 2, "runs fine": 2, "steady": 1,
                    "stays on": 1,
                },
                prior=0.35,
                severity=LOW,
            ),
            Cause(
                "Faulty sensor (oxygen, MAF or MAP sensor)",
                {
                    # steady / stays on fits most warning lights, so it only nudges this one a little
                    "drives normally": 2, "drives fine": 2, "runs fine": 2, "steady": 1, "stays on": 1, "mileage": 2,
                    "black smoke": 2, "check engine": 1,
                },
                prior=0.7,
            ),
            Cause(
                "Worn spark plugs or a failing ignition coil (misfire)",
                {"blink*": 4, "flash*": 4, "misfir*": 4, "rough idl*": 3, "shak*": 2, "at idle": 2, "jerk*": 2, "petrol": 1, "cng": 1},
                prior=0.8,
                fuels=SPARK_IGNITION,
            ),
            Cause(
                "Clogged air filter or dirty throttle body",
                {"less power": 2, "pickup": 2, "at idle": 1, "gradually": 1, "overdue": 2},
                prior=0.6,
            ),
            Cause(
                "Dirty fuel injectors or a weak fuel pump",
                {"hesitat*": 3, "sputter*": 3, "while accelerating": 2, "stall*": 2, "diesel": 1},
                prior=0.5,
            ),
            Cause(
                "Bad or contaminated fuel",
                {
                    "refuel*": 3, "petrol fill*": 2, "fill* petrol": 2, "new pump": 2, "adulterat*": 4, "wrong fuel": 5,
                    "knock*": 2, "jerk*": 1,
                },
                prior=0.2,
                severity=MEDIUM,
            ),
            Cause("Clogged catalytic converter or exhaust", {"rotten egg": 4, "sulphur": 4, "rattl*": 2, "less power": 1}, prior=0.15),
            Cause("Vacuum leak", {"hiss*": 4, "rough idl*": 2, "when the engine is cold": 1}, prior=0.3),
            Cause(
                "Something disturbed during the recent service (connector, hose, wrong part)",
                {"right after a service": 4, "after service": 4, "after the service": 4, "after servicing": 4},
                prior=0.15,
            ),
        ),
        service_code="engine-diagnostics",
        severity=MEDIUM,
        advice=(
            "A steady check engine light usually isn't an emergency, but get it scanned soon, the fault code tells the "
            "mechanic exactly where to look. If it starts blinking, slow down and avoid long drives, a misfire can "
            "damage the catalytic converter."
        ),
        escalations={"blink*": HIGH, "flash*": HIGH, "oil pressure light": CRITICAL, "oil light": CRITICAL, "temperature light": HIGH},
        research_focus=(
            "common check engine light / engine faults, software updates, service campaigns and recalls for this "
            "model, and current fuel quality issues in India (E20 petrol, adulteration)"
        ),
    ),
    IssueType(
        key="fuel_economy",
        label="Mileage & fuel economy",
        intro="A drop in mileage (average) can come from the fuel itself or from the car, let's check both.",
        keywords={
            "mileage": 5, "avg": 5, "average": 4, "fuel efficiency": 5, "fuel economy": 5, "kmpl": 5, "km per litre": 5,
            "fuel consumption": 5, "consuming more": 4, "more petrol": 4, "more diesel": 4, "more fuel": 4, "drinking": 3,
            "e20": 4, "ethanol": 4,
        },
        questions=(
            FUEL_QUESTION,
            Question(
                "drop",
                "Roughly how much has the mileage dropped?",
                ("A little, 10-15%", "Noticeably, 15-30%", "A lot, more than 30%", "Not sure"),
                # "gives 12 kmpl instead of 18", "dropped by half", "a lot"
                skip_if=("a little", "a lot", "more than 30", "10 15", "15 30", "percent", "half", "kmpl", "km per lit*"),
            ),
            Question(
                "onset",
                "When did you first notice it?",
                ("Right after a refuel", "After a service or repair", "Gradually over months", "Suddenly, in the last few days"),
                skip_if=("after refuel*", "after service", "gradually", "suddenly"),
            ),
            Question(
                "driving",
                "How is the car mostly driven these days?",
                ("Mostly city traffic", "Mostly highway", "A mix of both", "Short trips with the AC on"),
            ),
            Question(
                "symptoms",
                "Anything else you've noticed along with it?",
                ("Loss of pickup or jerks", "Check engine light", "Black smoke", "Burning smell or a hot wheel", "Nothing else"),
            ),
            Question(
                "upkeep",
                "When were the tyre pressure and the service last done?",
                ("Both done recently", "Tyre pressure not checked lately", "Service is overdue", "Not sure"),
            ),
        ),
        causes=(
            Cause(
                "Fuel quality - ethanol blended (E20) or adulterated petrol",
                {"right after a refuel": 4, "e20": 5, "ethanol": 4, "adulterat*": 4, "new pump": 3, "petrol": 1, "a little 10 15": 1},
                prior=0.6,
                severity=LOW,
            ),
            Cause(
                "Under-inflated tyres or wheel alignment out",
                {
                    "tyre pressure not checked": 4, "never check*": 3, "not check*": 3, "low pressure": 3, "low air": 3,
                    "pull*": 2, "tyre*": 1,
                },
                prior=0.7,
                severity=LOW,
            ),
            Cause(
                "Clogged air filter, old engine oil or service overdue",
                {
                    "service is overdue": 4, "not serviced": 4, "no service": 3, "overdue": 2, "gradually": 2,
                    "months back": 2, "months ago": 2, "year back": 2, "year ago": 2, "long time": 2, "loss of pickup": 1,
                },
                prior=0.8,
                severity=LOW,
            ),
            Cause(
                "Worn spark plugs or weak ignition",
                # a 30%+ drop is far more than E20 explains, usually something on the engine
                {"loss of pickup": 2, "jerks": 2, "a lot more than 30": 2, "gradually": 1, "petrol": 1, "cng": 2},
                prior=0.5,
                fuels=SPARK_IGNITION,
            ),
            Cause(
                "Faulty oxygen / MAF sensor or dirty injectors",
                {"check engine light": 4, "black smoke": 3, "a lot more than 30": 2, "diesel": 1},
                prior=0.5,
            ),
            Cause("Brakes dragging (sticking caliper)", {"burning smell or a hot wheel": 4, "hot wheel": 3, "burning smell": 3}, prior=0.3),
            Cause("Clutch slipping", {"revs": 2, "slip*": 3, "loss of pickup": 1}, prior=0.2),
            Cause(
                "Driving conditions - traffic, short trips and heavy AC use",
                {"mostly city traffic": 3, "short trips": 3, "ac on": 2, "a little 10 15": 2, "nothing else": 1},
                prior=0.6,
                severity=LOW,
            ),
            Cause("CNG kit needs tuning or has a small leak", {"cng": 3, "petrol cng": 2}, prior=0.25, fuels=("cng", "lpg")),
            Cause("Fuel leak", {"petrol smell": 4, "fuel smell": 4, "leak*": 3}, prior=0.1, severity=CRITICAL),
        ),
        service_code="mileage-checkup",
        severity=LOW,
        advice=(
            "Check the tyre pressures (the right values are on a sticker on the driver's door frame), fill up at a "
            "busy, trusted pump, and note the km per litre over the next two full tanks, it helps the mechanic a lot."
        ),
        escalations={"check engine light": MEDIUM, "black smoke": MEDIUM, "burning smell": MEDIUM, "fuel smell": CRITICAL, "petrol smell": CRITICAL},
        research_focus=(
            "current fuel quality news in India and how it affects mileage (E20 ethanol blended petrol, adulteration "
            "reports, CNG supply), plus common mileage complaints for this model"
        ),
        research_early=True,
    ),
    IssueType(
        key="overheating",
        label="Overheating & cooling",
        intro="Overheating can damage an engine quickly, so let's figure this out.",
        keywords={
            "overheat*": 5, "temperature gauge": 5, "temp gauge": 5, "temperature light": 4, "temperature": 2,
            "coolant": 4, "radiator": 4, "steam": 3, "boiling": 3, "heating up": 3, "sweet smell": 2, "hot": 1,
        },
        questions=(
            Question(
                "gauge",
                "How high does the temperature gauge go? Any steam from the bonnet?",
                ("Goes into the red", "Higher than usual, not red", "Steam from the bonnet", "Gauge looks normal"),
                skip_if=("steam", "red"),
            ),
            Question(
                "when",
                "When does it heat up?",
                ("In traffic / at idle", "On the highway / long drives", "Both", "Soon after starting"),
                skip_if=("traffic", "idl*", "signal*", "jam", "highway", "long drive*", "after starting", "uphill"),
            ),
            Question(
                "coolant",
                "Have you checked the coolant? Any green or pink puddle under the car?",
                ("Coolant is low", "Puddle under the car", "Coolant level is fine", "Haven't checked"),
                skip_if=("coolant is low", "low coolant", "puddle"),
            ),
            Question(
                "fan",
                "When it's hot and standing still, can you hear the radiator fan running?",
                ("Yes, the fan runs", "No, the fan doesn't come on", "Not sure"),
                skip_if=("fan",),
                only_if=("traffic", "idl*", "signal*", "jam", "both"),
            ),
            ONSET_QUESTION,
        ),
        causes=(
            Cause(
                "Low coolant due to a leak",
                {"coolant is low": 4, "low coolant": 4, "puddle": 3, "leak*": 3, "sweet smell": 3, "steam": 2, "green": 1, "pink": 1},
                prior=1.0,
            ),
            Cause("Radiator fan not working", {"in traffic": 3, "at idle": 2, "fan doesnt come on": 5}, prior=0.7),
            Cause("Faulty thermostat", {"soon after starting": 3, "coolant level is fine": 2, "fluctuat*": 3, "up and down": 3}, prior=0.6),
            Cause("Clogged radiator", {"highway": 3, "long drive*": 3, "both": 1, "gradually": 1}, prior=0.5),
            Cause("Failing water pump", {"whin*": 2, "leak*": 1, "puddle": 1, "front of the engine": 2}, prior=0.4),
            Cause(
                "Head gasket failure",
                {"white smoke": 3, "milky": 4, "bubbl*": 3, "coolant disappear*": 3},
                prior=0.15,
                severity=CRITICAL,
            ),
        ),
        service_code="cooling-system",
        severity=HIGH,
        advice="If the gauge goes near the red, pull over and switch off. Don't open the radiator cap while it's hot, the coolant is under pressure.",
        escalations={"red": CRITICAL, "steam": HIGH},
        research_focus="cooling system recalls or known overheating complaints for this model",
    ),
    IssueType(
        key="transmission",
        label="Clutch & gearbox",
        intro="Got it, sounds like clutch or gearbox trouble.",
        keywords={
            "clutch": 5, "gear*": 4, "gearbox": 5, "transmission": 5, "shift*": 2, "amt": 3, "cvt": 3,
            "automatic": 1, "slip*": 2, "neutral": 2, "reverse": 1,
        },
        questions=(
            Question(
                "gearbox_type",
                "Is it a manual, automatic, AMT or CVT?",
                ("Manual", "Automatic", "AMT", "CVT"),
                skip_if=("manual", "automatic", "amt", "cvt", "clutch*"),
            ),
            Question(
                "symptom",
                "What exactly happens?",
                ("Hard to shift / gears grind", "Engine revs but car doesn't speed up", "Jerks while shifting", "Noise in neutral that stops when clutch is pressed"),
                skip_if=("slip*", "revs", "grind*"),
            ),
            Question(
                "clutch_point",
                "Where does the clutch engage now?",
                ("Very high up", "Normal", "Near the floor"),
                only_if=("manual", "clutch*"),
            ),
            Question(
                "clutch_age",
                "Roughly how many km since the clutch was last replaced?",
                ("Under 30,000 km", "30,000 - 60,000 km", "Over 60,000 km / never", "Not sure"),
                skip_if=("clutch plate never", "clutch never", "clutch was changed", "clutch replaced", "new clutch"),
                only_if=("manual", "clutch*"),
            ),
            ONSET_QUESTION,
        ),
        causes=(
            Cause(
                "Worn clutch plate",
                {"revs but": 4, "slip*": 4, "very high": 4, "burning smell": 2, "doesnt speed up": 3, "pickup": 1, "over 60000": 3},
                prior=1.0,
            ),
            Cause(
                "Clutch hydraulics or cable problem",
                {"near the floor": 4, "hard to shift": 2, "grind*": 1, "soft clutch": 3, "clutch pedal": 1},
                prior=0.6,
            ),
            Cause("Worn clutch release bearing", {"noise in neutral": 4, "stops when clutch": 3, "whin*": 1}, prior=0.4),
            Cause("Old or low gearbox oil / ATF", {"jerk*": 3, "delay*": 2, "late shift*": 3, "automatic": 1, "cvt": 1, "whin*": 2}, prior=0.6),
            Cause("Worn synchro rings", {"grind*": 3, "hard to shift": 2, "second gear": 1, "third gear": 1}, prior=0.4),
            Cause("AMT actuator needs calibration or a software update", {"amt": 3, "jerk*": 1, "gear indicator": 2}, prior=0.3),
        ),
        service_code="clutch-transmission",
        severity=MEDIUM,
        advice="Go easy on the clutch and avoid heavy loads or steep climbs until it's checked, a slipping clutch wears out fast.",
        research_focus="known clutch / gearbox (AMT, CVT) problems, software updates and recalls for this model",
    ),
    IssueType(
        key="suspension",
        label="Suspension & steering",
        intro="Suspension and steering noises can usually be pinned down with a few details.",
        keywords={
            "suspension": 5, "shock*": 3, "strut*": 3, "bump*": 2, "speed breaker*": 3, "pothole*": 3,
            "steering": 2, "clunk*": 3, "bouncy": 3, "bounc*": 2, "creak*": 2, "wander*": 2, "knock*": 1,
        },
        questions=(
            Question(
                "symptom",
                "What kind of noise or feeling is it?",
                ("Clunk / knock over bumps", "Creak or click when turning", "Car bounces a lot", "Steering pulls or feels loose", "Steering is very heavy"),
                skip_if=("clunk*", "bounc*", "creak*", "heavy steering", "hard steering"),
            ),
            Question(
                "when",
                "When do you notice it most?",
                ("Over speed breakers / potholes", "While turning the wheel", "At high speed", "All the time"),
                skip_if=("speed breaker*", "pothole*", "while turning"),
            ),
            Question(
                "corner",
                "Can you tell which corner it's coming from?",
                ("Front", "Rear", "Front left", "Front right", "Not sure"),
                skip_if=("front", "rear"),
            ),
            Question(
                "impact",
                "Did the car hit a big pothole, kerb or have an accident recently?",
                ("Yes, a hard hit recently", "No, it came on slowly", "Not sure"),
            ),
        ),
        causes=(
            Cause("Worn shock absorbers / struts", {"bounc*": 4, "bouncy": 4, "dip*": 2, "leak*": 1, "came on slowly": 1}, prior=0.8),
            Cause(
                "Worn suspension bushes or stabiliser links",
                {"clunk*": 3, "knock*": 2, "speed breaker*": 2, "pothole*": 2, "creak*": 2, "came on slowly": 1},
                prior=1.0,
            ),
            Cause("Worn ball joint or tie rod end", {"loose": 3, "wander*": 3, "front": 1, "clunk*": 1}, prior=0.5, severity=HIGH),
            Cause("Worn CV joint / drive shaft", {"while turning": 3, "click*": 3, "creak or click": 2}, prior=0.5),
            Cause("Wheel alignment out or bent suspension part", {"pull*": 3, "off centre": 3, "off center": 3, "hard hit": 3, "high speed": 1}, prior=0.6),
            Cause("Power steering fault", {"heavy": 4, "hard steering": 4, "steering light": 3, "eps": 3, "whin*": 2}, prior=0.4),
        ),
        service_code="suspension-steering",
        severity=MEDIUM,
        advice="Slow down over speed breakers and potholes. If the steering feels loose, don't take it on the highway until it's checked.",
        escalations={"loose": HIGH, "steering locked": CRITICAL},
        research_focus="suspension or steering recalls and common complaints for this model",
    ),
    IssueType(
        key="tyres",
        label="Tyres & wheels",
        intro="Tyres are the only thing holding you to the road, good that you're checking.",
        keywords={
            "tyre*": 5, "tire*": 5, "puncture*": 5, "flat": 3, "wheel*": 2, "alignment": 4, "balanc*": 3,
            "wobbl*": 3, "tread": 4, "air pressure": 4, "tpms": 5, "rim": 3,
            "vibrat*": 2, "high speed": 2, "shak*": 1, "steering wheel shak*": 4, "steering shak*": 4, "at speed": 3,
            "kmph": 2,
        },
        questions=(
            Question(
                "symptom",
                "What's happening with the tyres?",
                ("Vibration at speed", "A tyre keeps losing air", "Uneven or fast wear", "Car pulls to one side"),
                skip_if=("vibrat*", "shak*", "wobbl*", "losing air", "puncture*", "flat", "uneven", "pull*"),
            ),
            Question(
                "speed",
                "At what speed does the vibration show up?",
                ("Below 60 km/h", "60 to 100 km/h", "Above 100 km/h"),
                skip_if=("kmph", "km h", "above", "below"),
                only_if=("vibrat*", "shak*", "wobbl*"),
            ),
            Question(
                "pressure",
                "When did you last check the tyre pressure?",
                ("In the last 2 weeks", "About a month ago", "Can't remember"),
                skip_if=("flat", "puncture*"),
            ),
            Question(
                "age",
                "How old are the tyres?",
                ("Under 2 years", "3 to 5 years", "Over 5 years", "Don't remember"),
                skip_if=("year* old", "months old", "new tyre*", "tyres are new", "changed the tyres"),
            ),
        ),
        causes=(
            Cause("Wheels need balancing", {"vibrat*": 2, "60 to 100": 3, "above 100": 3, "high speed": 3, "steering shak*": 2}, prior=1.0),
            Cause("Wheel alignment out", {"pull*": 3, "uneven": 3, "inner edge": 3, "outer edge": 3, "fast wear": 2}, prior=0.8),
            Cause("Slow puncture or leaking valve", {"losing air": 4, "puncture*": 3, "flat": 2, "tpms": 2, "nail": 3}, prior=0.8),
            Cause("Wrong tyre pressure", {"cant remember": 3, "about a month": 1, "uneven": 1, "pull*": 1}, prior=0.4, severity=LOW),
            Cause("Damaged or aged tyre (bulge, cracks)", {"bulg*": 4, "crack*": 3, "over 5 years": 3, "wobbl*": 2}, prior=0.4, severity=HIGH),
            Cause("Bent rim", {"pothole*": 2, "below 60": 2, "rim": 3, "wobbl*": 2}, prior=0.3),
        ),
        service_code="wheel-alignment",
        severity=MEDIUM,
        advice="Check the tyre pressures (the correct values are on a sticker on the driver's door frame) and keep speeds moderate until it's sorted.",
        escalations={"bulg*": HIGH},
        research_focus="tyre or wheel related recalls and common complaints for this model",
    ),
    IssueType(
        key="ac",
        label="AC & cabin",
        intro="AC trouble, let's see what's going on.",
        keywords={
            "ac": 5, "a c": 4, "air con*": 5, "aircon": 5, "air condition*": 5, "blower": 4, "cooling": 1,
            "compressor": 3, "heater": 3, "defog*": 3, "musty": 3, "cabin": 2, "vent*": 2,
        },
        questions=(
            Question(
                "symptom",
                "What's the AC problem?",
                ("Not cooling enough", "Blowing warm air", "Weak airflow", "Bad smell", "Noise when AC is on"),
                skip_if=("not cooling", "warm air", "hot air", "smell*", "airflow"),
            ),
            Question(
                "when",
                "Is it worse in traffic or while driving?",
                ("Worse in traffic / idle", "Worse while driving", "Same all the time"),
            ),
            Question(
                "last_service",
                "When was the AC last serviced or re-gassed?",
                ("Within a year", "1 to 2 years ago", "More than 2 years ago", "Never / not sure"),
            ),
            ONSET_QUESTION,
        ),
        causes=(
            Cause("Low refrigerant gas (small leak)", {"not cooling": 3, "warm air": 3, "hot air": 3, "more than 2 years": 2, "never": 1, "gradual*": 2}, prior=1.0),
            Cause("Dirty cabin filter or blocked evaporator", {"weak airflow": 4, "bad smell": 3, "musty": 3, "smell*": 1}, prior=0.8),
            Cause("Condenser fan not working / dirty condenser", {"worse in traffic": 4, "idle": 2}, prior=0.6),
            Cause("AC compressor or clutch fault", {"noise when ac": 4, "compressor": 3, "click*": 2, "warm air": 1, "suddenly": 1}, prior=0.4),
            Cause("Blower motor or resistor fault", {"blower": 3, "only works on": 4, "weak airflow": 2}, prior=0.3),
        ),
        service_code="ac-service",
        severity=LOW,
        advice=(
            "Safe to drive. Until it's checked, park in the shade and drive the first minute with the windows down "
            "before switching to recirculation, it cools the cabin faster. If there's a musty smell, run the fan "
            "with the AC off for a few minutes before parking."
        ),
        research_focus="common AC complaints or recalls for this model",
    ),
    IssueType(
        key="electrical",
        label="Electrical & lights",
        intro="Electrical faults can be fiddly, a few details will help the mechanic a lot.",
        keywords={
            "electric*": 3, "wiring": 4, "wire*": 2, "fuse*": 4, "headlight*": 4, "tail light*": 4, "indicator*": 3,
            "horn": 4, "power window*": 5, "window*": 1, "wiper*": 3, "central lock*": 5, "music system": 3,
            "infotainment": 3, "short circuit": 5, "battery drain*": 3, "rats": 2, "rat": 2, "light*": 1,
        },
        questions=(
            Question(
                "what",
                "What exactly isn't working?",
                ("Lights / indicators", "Power windows / central locking", "Horn / wipers", "Battery drains overnight", "Several things at once"),
                skip_if=("headlight*", "indicator*", "power window*", "horn", "wiper*", "drain*"),
            ),
            Question(
                "pattern",
                "Is it completely dead, or does it work on and off?",
                ("Completely dead", "Works on and off", "Works but weak / dim"),
                skip_if=("on and off", "sometimes", "dim*", "stopped working", "not working at all", "dead", "completely"),
            ),
            Question(
                "recent",
                "Any accessories fitted recently (music system, extra lights, alarm), or water / rats getting in?",
                ("Accessories fitted recently", "Water got in", "Rats seen around the car", "None of these"),
                skip_if=("rats", "rat", "water"),
            ),
            ONSET_QUESTION,
        ),
        causes=(
            Cause("Blown fuse or faulty relay", {"completely dead": 3, "fuse*": 3, "horn": 1, "stopped working": 2, "suddenly": 1}, prior=1.0),
            Cause("Loose connection or damaged wiring", {"on and off": 4, "sometimes": 2, "flicker*": 3, "water got in": 3, "rats": 4, "rat": 4, "rodent*": 4, "chew*": 3}, prior=0.8),
            Cause("Battery drain from an accessory", {"drains overnight": 4, "accessories fitted": 4, "drain*": 2}, prior=0.6),
            Cause("Faulty switch or motor (window motor, wiper motor)", {"power window*": 2, "slow*": 2, "one window": 3, "only one": 2}, prior=0.6),
            Cause("Weak alternator or battery", {"dim*": 3, "weak": 2, "several things at once": 3, "battery light": 3, "gradually": 1}, prior=0.5),
        ),
        service_code="battery-electrical",
        severity=LOW,
        advice="If it's lights or indicators, avoid night driving until they work. If you smell burning plastic, disconnect the battery.",
        escalations={"burning smell": HIGH, "burning plastic": HIGH, "short circuit": HIGH, "sparks": CRITICAL},
        research_focus="electrical or wiring recalls and common complaints (including rodent damage) for this model",
    ),
    IssueType(
        key="exhaust",
        label="Smoke & exhaust",
        intro="Smoke colour tells us a lot. Couple of questions:",
        keywords={
            "smoke": 4, "smok*": 4, "exhaust": 5, "silencer": 5, "muffler": 5, "tailpipe": 5, "fumes": 3,
            "white smoke": 5, "black smoke": 5, "blue smoke": 5,
        },
        questions=(
            Question(
                "colour",
                "What colour is the smoke?",
                ("White", "Blue / grey", "Black", "No smoke, just a loud exhaust"),
                skip_if=("white", "blue", "grey", "gray", "black", "loud"),
            ),
            FUEL_QUESTION,
            Question(
                "when",
                "When do you see it?",
                ("Only at cold start, then it clears", "All the time", "When accelerating hard", "After idling for a while"),
            ),
            Question(
                "fluids",
                "Is the car using up oil or coolant between services?",
                ("Oil level drops", "Coolant level drops", "Both levels stay fine", "Haven't checked"),
            ),
        ),
        causes=(
            Cause("Condensation, normal on a cold start", {"cold start": 4, "then it clears": 3, "white": 1, "winter": 2}, prior=0.6, severity=LOW),
            Cause("Engine burning oil (worn piston rings or valve seals)", {"blue": 4, "grey": 3, "gray": 3, "oil level drops": 4}, prior=0.7),
            Cause("Engine running rich (injectors, air filter or sensor)", {"black": 4, "accelerating hard": 2, "mileage": 2, "diesel": 1}, prior=0.8),
            Cause("Clogged diesel particulate filter (DPF)", {"diesel": 2, "black": 1, "short trips": 2, "dpf": 5}, prior=0.2),
            Cause(
                "Coolant burning, possible head gasket leak",
                {"coolant level drops": 4, "white": 2, "all the time": 2, "sweet smell": 3},
                prior=0.3,
                severity=CRITICAL,
            ),
            Cause("Exhaust leak or damaged silencer", {"loud": 3, "rattl*": 3, "hole": 3, "silencer": 2}, prior=0.5, severity=LOW),
            Cause("Turbocharger oil seal leak", {"turbo": 4, "whistl*": 3, "blue": 1, "diesel": 1}, prior=0.2),
        ),
        service_code="engine-diagnostics",
        severity=MEDIUM,
        advice="Keep an eye on the oil and coolant levels, and on the temperature gauge, until it's checked.",
        research_focus="known smoke / exhaust / DPF problems and recalls for this model, and fuel quality issues in India",
    ),
    IssueType(
        key="leaks",
        label="Fluid leaks",
        intro="The colour and position of a leak usually gives it away.",
        keywords={"leak*": 5, "drip*": 4, "puddle": 4, "fluid": 2, "under the car": 3, "spot*": 1},
        questions=(
            Question(
                "colour",
                "What colour is the fluid?",
                ("Black / dark brown", "Green, pink or orange", "Red", "Clear like water", "Light yellow-brown"),
                skip_if=("black", "green", "pink", "orange", "red", "clear", "water"),
            ),
            Question(
                "location",
                "Where is the puddle?",
                ("Front / engine area", "Middle of the car", "Near one wheel", "Rear"),
                skip_if=("front", "rear", "back side", "middle", "wheel*", "engine area", "under the engine", "bonnet"),
            ),
            Question(
                "amount",
                "How much is leaking?",
                ("A few drops", "Small puddle overnight", "Keeps dripping while parked"),
                skip_if=("few drops", "small puddle", "big puddle", "dripping"),
            ),
            ONSET_QUESTION,
        ),
        causes=(
            Cause("Engine oil leak (gasket, seal or drain plug)", {"black": 3, "dark brown": 3, "engine area": 2, "oil": 2, "right after a service": 2}, prior=1.0),
            Cause("Coolant leak (hose, radiator or water pump)", {"green": 4, "pink": 4, "orange": 3, "sweet": 2, "coolant": 3}, prior=0.8),
            Cause("Gearbox or power steering fluid leak", {"red": 4, "middle": 2}, prior=0.5),
            Cause("Brake fluid leak", {"yellow*": 3, "near one wheel": 4, "soft pedal": 4}, prior=0.3, severity=CRITICAL),
            Cause("AC condensation water, this is normal", {"clear": 4, "water": 2, "ac": 2}, prior=0.6, severity=LOW),
            Cause("Fuel leak", {"petrol": 4, "fuel": 3, "diesel": 3, "smell*": 1}, prior=0.2, severity=CRITICAL),
        ),
        service_code="leak-inspection",
        severity=MEDIUM,
        advice="Put a sheet of paper or cardboard under the car overnight, it makes the leak easy to spot for the mechanic. Check the oil and coolant levels before driving.",
        escalations={"petrol smell": CRITICAL, "fuel smell": CRITICAL, "fuel leak": CRITICAL, "petrol leak": CRITICAL},
        research_focus="known oil, coolant or fuel leak problems and recalls for this model",
    ),
    IssueType(
        key="routine",
        label="Routine service",
        intro="Happy to help with regular maintenance.",
        keywords={
            "servic*": 2, "oil change": 5, "maintenance": 4, "service due": 5, "due for service": 5, "check up": 3,
            "checkup": 3, "general check": 4, "road trip": 3, "long trip": 3, "inspection": 2,
        },
        questions=(
            Question(
                "last_service",
                "How long since the last service?",
                ("Less than 10,000 km", "10,000 to 20,000 km", "More than 20,000 km / over a year", "Not sure"),
                skip_if=("last service", "last one", "serviced at", "service at", "service was", "since the service"),
            ),
            Question(
                "extra",
                "Anything specific you want checked along with it?",
                ("Brakes", "AC", "Battery", "Nothing specific"),
            ),
        ),
        causes=(
            Cause("Periodic service due (oil, filters, fluids)", {"more than 20*": 3, "over a year": 3, "10000 to 20000": 2, "oil change": 3, "service due": 3}, prior=1.0, severity=LOW),
            Cause("Pre-trip inspection", {"trip": 4, "highway": 1}, prior=0.3, severity=LOW),
            Cause("General health check", {"not sure": 1, "check up": 2, "checkup": 2, "nothing specific": 1}, prior=0.4, severity=LOW),
        ),
        service_code="periodic-service",
        severity=LOW,
        advice="Most cars need a service every 10,000 km or once a year, whichever comes first. Check your owner's manual for the exact schedule.",
    ),
]

ISSUE_TYPES_BY_KEY = {issue.key: issue for issue in ISSUE_TYPES}


@dataclass(frozen=True)
class TriageQuestion:
    """Clarifying question for vague complaints like "my car makes a weird noise"."""

    patterns: tuple
    text: str
    options: tuple  # (label, issue key)


TRIAGE_QUESTIONS = {
    "noise": TriageQuestion(
        ("noise*", "sound*", "rattl*", "whin*", "humming", "ticking", "tapping"),
        "When do you hear the noise?",
        (
            ("When braking", "brakes"),
            ("Over bumps or while turning", "suspension"),
            ("When accelerating", "engine"),
            ("While changing gears", "transmission"),
            ("When starting the car", "starting"),
            ("When the AC is on", "ac"),
        ),
    ),
    "vibration": TriageQuestion(
        ("vibrat*", "shak*", "shudder*", "wobbl*"),
        "When does the car vibrate or shake?",
        (
            ("When braking", "brakes"),
            ("At high speed", "tyres"),
            ("At idle / standing still", "engine"),
            ("While changing gears", "transmission"),
        ),
    ),
    "smell": TriageQuestion(
        ("smell*", "odour", "odor", "stink*"),
        "What kind of smell is it?",
        (
            ("Burning rubber / clutch smell", "transmission"),
            ("Burning plastic smell", "electrical"),
            ("Burning oil smell", "leaks"),
            ("Petrol / fuel smell", "leaks"),
            ("Sweet smell", "overheating"),
            ("Musty smell from the AC", "ac"),
        ),
    ),
    "warning_light": TriageQuestion(
        ("warning light*", "dashboard light*", "light on", "light is on", "light came on", "symbol"),
        "Which warning light is on?",
        (
            ("Check engine light", "engine"),
            ("Battery light", "starting"),
            ("Temperature light", "overheating"),
            ("ABS / brake light", "brakes"),
            ("Tyre pressure light", "tyres"),
            ("Oil pressure light", "engine"),
        ),
    ),
}


# Things that need a safety warning straight away, no matter what else is going on.
SAFETY_ALERTS = [
    (
        ("fire", "flame*", "smoke from the bonnet", "smoke from bonnet", "smoke from under the hood", "sparks"),
        "Safety first: if there's fire or smoke from under the bonnet, switch off the engine, get everyone out and "
        "stay well away from the car. Call 112 if you see flames. Don't open the bonnet.",
    ),
    (
        ("petrol smell*", "fuel smell*", "smell* of petrol", "smell* of fuel", "smell* petrol", "smell* fuel",
         "fuel leak*", "petrol leak*", "diesel leak*", "leaking petrol", "leaking fuel"),
        "A fuel smell or leak is a fire risk. Don't start the car, don't smoke near it, and keep it parked in the open "
        "until a mechanic has looked at it.",
    ),
    (
        ("no brakes", "brake failure", "brakes failed", "brakes not working", "brake not working"),
        "If the brakes fail while driving: pump the pedal, shift to a lower gear, use the handbrake gently and steer "
        "to a safe spot. Please don't drive the car again until it's repaired, we can send a mechanic to you.",
    ),
    (
        ("oil pressure light", "oil light", "red oil"),
        "A red oil pressure light means the engine may not be getting oil. Pull over and switch off as soon as it's "
        "safe, driving with it on can destroy the engine within minutes.",
    ),
]


def severity_rank(severity):
    return SEVERITY_ORDER.index(severity) if severity in SEVERITY_ORDER else 1


def higher_severity(a, b):
    return a if severity_rank(a) >= severity_rank(b) else b
