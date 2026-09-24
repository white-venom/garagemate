from django.test import SimpleTestCase

from chat.bot import intents
from chat.bot.understand import looks_non_english
from chat.bot.vehicle import extract_vehicle_details
from core.text import mentions, normalize


class TextMatchingTests(SimpleTestCase):
    def test_prefix_match(self):
        self.assertTrue(mentions(normalize("Braking feels weird"), "brak*"))

    def test_prefix_inside_phrase(self):
        self.assertTrue(mentions(normalize("I smell petrol in the cabin"), "smell* petrol"))

    def test_negation_is_ignored(self):
        self.assertFalse(mentions(normalize("there is no grinding noise"), "grind*"))

    def test_negation_does_not_leak_into_next_clause(self):
        self.assertTrue(mentions(normalize("it doesn't start and the battery is old"), "battery"))

    def test_numbers_with_commas(self):
        self.assertEqual(normalize("60,000 km"), "60000 km")

    def test_not_giving_is_a_complaint(self):
        # "not giving the mileage" is the problem itself, not "no mileage problem"
        self.assertTrue(mentions(normalize("my car is not giving the mileage it used to"), "mileage"))
        self.assertTrue(mentions(normalize("ac is not cooling"), "cool*"))


class IntentTests(SimpleTestCase):
    def check(self, func, text):
        return func(normalize(text))

    def test_greeting(self):
        self.assertTrue(self.check(intents.is_greeting, "Hello there"))
        self.assertFalse(self.check(intents.is_greeting, "hello my brakes are squeaking since last week badly"))

    def test_car_related(self):
        for text in ["my clutch is slipping", "check engine light came on", "my creta makes a noise"]:
            self.assertTrue(self.check(intents.is_car_related, text), text)

    def test_off_topic(self):
        for text in ["write me a poem", "what's the weather in mumbai", "who will win the cricket match"]:
            self.assertTrue(self.check(intents.is_off_topic, text), text)
        self.assertFalse(self.check(intents.is_off_topic, "my car battery died"))

    def test_joke_about_car_is_still_off_topic(self):
        self.assertTrue(self.check(intents.is_off_topic, "tell me a joke about cars"))

    def test_booking_and_yes_no(self):
        self.assertTrue(self.check(intents.wants_booking, "please book a mechanic"))
        self.assertTrue(self.check(intents.is_yes, "yes please"))
        self.assertTrue(self.check(intents.is_no, "not right now"))

    def test_language_request(self):
        self.assertEqual(self.check(intents.language_request, "can you talk in hindi"), "hi")
        self.assertEqual(self.check(intents.language_request, "hinglish please"), "hinglish")
        self.assertEqual(self.check(intents.language_request, "english"), "en")
        self.assertIsNone(self.check(intents.language_request, "the hindi radio in my car stopped working after the battery died"))

    def test_free_text_answer_matches_an_option(self):
        light = ("Steady, stays on all the time", "Blinking / flashing", "Comes and goes")
        years = ("Within the last year", "1 to 2 years ago", "More than 2 years ago / never", "Not sure")
        fuel = ("Petrol", "Diesel", "CNG", "Petrol + CNG")
        self.assertEqual(intents.match_option(normalize("it stays on all the time"), light), light[0])
        self.assertIsNone(intents.match_option(normalize("it doesn't blink"), light))
        self.assertIsNone(intents.match_option(normalize("3 years ago"), years))
        self.assertEqual(intents.match_option(normalize("more than 2 years"), years), years[2])
        # one shared word isn't enough in a longer answer, unless the rest just repeats the question
        before = ("Car stood unused for days", "Lights or music were left on", "Nothing like that")
        self.assertIsNone(intents.match_option(normalize("the lights are a bit dim"), before))
        pedal = ("Soft / goes down too far", "Vibrates or pulses", "Feels normal")
        self.assertEqual(intents.match_option(normalize("pedal is soft"), pedal, "How does the brake pedal feel?"), pedal[0])
        self.assertEqual(intents.match_option(normalize("petrol"), fuel), "Petrol")
        self.assertEqual(intents.match_option(normalize("petrol and cng both"), fuel), "Petrol + CNG")

    def test_hinglish_is_spotted(self):
        self.assertTrue(looks_non_english("meri gaadi ka avg kam ho gaya hai"))
        self.assertTrue(looks_non_english("गाड़ी स्टार्ट नहीं हो रही"))
        self.assertFalse(looks_non_english("my car is making a noise"))

    def test_triage_topic(self):
        self.assertEqual(self.check(intents.triage_topic, "there's a strange noise"), "noise")
        self.assertEqual(self.check(intents.triage_topic, "some warning light is on"), "warning_light")


class VehicleExtractionTests(SimpleTestCase):
    def test_full_description(self):
        details = extract_vehicle_details("2017 Maruti Swift petrol, about 65,000 km")
        self.assertEqual(details["make"], "Maruti Suzuki")
        self.assertEqual(details["model"], "Swift")
        self.assertEqual(details["year"], 2017)
        self.assertEqual(details["odometer_km"], 65000)
        self.assertEqual(details["fuel_type"], "petrol")

    def test_model_implies_make(self):
        details = extract_vehicle_details("my creta has done 1.2 lakh km")
        self.assertEqual(details["make"], "Hyundai")
        self.assertEqual(details["odometer_km"], 120000)

    def test_short_forms(self):
        self.assertEqual(extract_vehicle_details("80k km")["odometer_km"], 80000)
        self.assertEqual(extract_vehicle_details("hyundai i20 2015")["model"], "i20")

    def test_ambiguous_model_needs_make(self):
        self.assertNotIn("model", extract_vehicle_details("changed the spark plugs in city traffic"))
        self.assertEqual(extract_vehicle_details("honda city 2012")["model"], "City")

    def test_registration_number(self):
        self.assertEqual(extract_vehicle_details("my swift, MH 12 AB 1234")["registration_number"], "MH12AB1234")
        self.assertEqual(extract_vehicle_details("dl-3c-ab-1234")["registration_number"], "DL3CAB1234")
        # not a state code, just an AC and a year
        self.assertNotIn("registration_number", extract_vehicle_details("ac 12 2019"))

    def test_dual_fuel_is_cng(self):
        self.assertEqual(extract_vehicle_details("Petrol + CNG")["fuel_type"], "cng")

    def test_km_is_not_a_year(self):
        self.assertNotIn("year", extract_vehicle_details("done 2000 km since service"))
