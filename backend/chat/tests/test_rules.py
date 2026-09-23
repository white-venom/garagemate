from django.test import SimpleTestCase

from chat.bot import intents
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

    def test_km_is_not_a_year(self):
        self.assertNotIn("year", extract_vehicle_details("done 2000 km since service"))
