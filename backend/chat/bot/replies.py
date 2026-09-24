"""Canned replies. Keeping them here so the flow code stays readable."""

GREETING = (
    "Hi{name}! I'm GarageMate, your virtual mechanic. Tell me what's going on with {car}: strange noises, "
    "warning lights, smells, leaks, starting trouble, anything that feels off.\n\n"
    "You can also send a photo, a short video, or record the sound it's making."
)


def greeting(name="", car=""):
    return GREETING.format(name=f" {name}" if name else "", car=f"your {car}" if car else "your car")


STARTER_PROMPTS = [
    "Brakes are squeaking",
    "Car won't start",
    "AC isn't cooling",
    "Check engine light is on",
]

OFF_TOPIC = (
    "Sorry, I can only help with cars: breakdowns, strange noises, warning lights, servicing and repairs. "
    "Is something going on with your car that I can look at?"
)

NUDGE = "I'm here to help with car trouble. What's going on with your car?"

NEED_MORE_DETAIL = (
    "Can you tell me a bit more about the problem? For example what you notice (noise, smell, vibration, "
    "warning light, leak), when it happens, and since when."
)

ASK_WHAT_PROBLEM = "Thanks, I've added that to your case. What problem are you noticing with the car?"

TRIAGE_INTRO = "Okay, let's narrow it down."

THANKS = "Happy to help! If anything else comes up with the car, just message me here."

BOOKING_DECLINED = (
    "No problem. You can still book from the diagnosis card whenever you're ready. Anything else I can help with?"
)

NO_AI_FOR_QUESTIONS = (
    "I can't answer general questions like that at the moment. If something is wrong with the car, describe "
    "the symptoms and I'll help you work out what it is."
)

AI_UNAVAILABLE = (
    "Sorry, I couldn't look that up just now. If there's a problem with the car, describe the symptoms "
    "(noise, smell, warning light, when it happens) and I'll walk you through it."
)

MEDIA_SAVED = (
    "I've attached your {kinds} to this case so the mechanic can check it during the inspection."
)

MEDIA_NOT_CAR = (
    "I had a look at your {kind}, but it doesn't seem to show a car or car part. "
    "If you meant to send something else, feel free to try again."
)

SOMETHING_WENT_WRONG = (
    "Sorry, something went wrong on my side while working on that. Could you send it again?"
)

NONE_OF_THESE = (
    "No problem, you don't have to pick one of those. Tell me in your own words what's happening with the car: "
    "what you notice, when it happens and since when. You can also send a photo or record the sound."
)

LANGUAGE_SWITCHED = "Sure, I'll reply in {language} from now on."

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "hinglish": "Hinglish"}

NOTED_NONE = "No problem, let's move on."

GOT_IT = "Got it, I've added that to your case."

CAR_NOTED = "Thanks, I've noted the car."

UPDATED_DIAGNOSIS = "Thanks, that helps. Here's the updated picture:"

NOTED = "Okay, noted. Anything else you'd like to know about it, or shall I book the mechanic?"

ADDED_FOR_MECHANIC = "Thanks, I've added that to your case so the mechanic knows before the visit."

ENGLISH_ONLY = "Sorry, I can only reply in English at the moment."

RESEARCH_INTRO = "Before the next questions, here's what's worth knowing about {fuel} right now:"

RESEARCH_OUTRO = "Now a few questions to check the car itself."

# used when the web research isn't available (no API key / quota), general facts only
FUEL_NOTES = {
    "petrol": (
        "Worth knowing: most pumps in India now sell E20 petrol (20% ethanol). The official estimate is a 2-6% "
        "drop in mileage, a bit more on older cars that weren't designed for E20. A bigger drop than that usually "
        "points to something on the car, so let's check."
    ),
    "cng": (
        "Worth knowing: CNG mileage depends a lot on the kit being tuned right and on the gas pressure at the "
        "station. A sudden drop after a refill or a kit service is a good clue."
    ),
    "diesel": (
        "Worth knowing: a diesel's mileage drops mostly from clogged air or fuel filters, dirty injectors and "
        "under-inflated tyres. Fuel quality issues are rarer but do happen at some pumps."
    ),
}

KIND_NAMES = {"image": "photo", "audio": "recording", "video": "video"}
