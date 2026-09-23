"""
Booking logic: slot availability and auto-assigning a free mechanic.
All plain Django, no AI anywhere near this.
"""

import logging

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from core.exceptions import Conflict

from .models import Booking, Mechanic

logger = logging.getLogger(__name__)

MAX_DAYS_AHEAD = 30
# need at least this many hours between booking and the start of the slot
MIN_NOTICE_HOURS = 1

ACTIVE = ~Q(status=Booking.Status.CANCELLED)


def slot_start_hour(time_slot):
    return int(time_slot.split("-")[0])


def slot_has_passed(day, time_slot, now=None):
    now = timezone.localtime(now)
    if day != now.date():
        return day < now.date()
    return now.hour + MIN_NOTICE_HOURS >= slot_start_hour(time_slot)


def slot_availability(day):
    """Remaining capacity for each slot on a day = free mechanics."""
    mechanic_count = Mechanic.objects.filter(is_active=True).count()
    taken = dict(
        Booking.objects.filter(ACTIVE, scheduled_date=day, mechanic__is_active=True)
        .values_list("time_slot")
        .annotate(total=Count("id"))
    )
    closed = day.weekday() == 6

    slots = []
    for slot in Booking.TimeSlot:
        remaining = max(mechanic_count - taken.get(slot.value, 0), 0)
        slots.append(
            {
                "value": slot.value,
                "label": slot.label,
                "remaining": remaining,
                "available": remaining > 0 and not closed and not slot_has_passed(day, slot.value),
            }
        )
    return slots


def _free_mechanics(day, time_slot):
    busy = Booking.objects.filter(ACTIVE, scheduled_date=day, time_slot=time_slot).values("mechanic_id")
    # least busy mechanic that day first, so work is spread out
    return (
        Mechanic.objects.filter(is_active=True)
        .exclude(id__in=busy)
        .annotate(load=Count("bookings", filter=Q(bookings__scheduled_date=day) & ~Q(bookings__status=Booking.Status.CANCELLED)))
        .order_by("load", "id")
    )


def create_booking(**data):
    """
    Assign the least busy free mechanic and save the booking.

    The unique constraint on (mechanic, date, slot) protects us if two people
    grab the last mechanic at the same moment: the loser gets an IntegrityError
    and we just try the next free mechanic.
    """
    for mechanic in _free_mechanics(data["scheduled_date"], data["time_slot"]):
        try:
            with transaction.atomic():
                return Booking.objects.create(mechanic=mechanic, **data)
        except IntegrityError:
            logger.info("Mechanic %s got booked in the meantime, trying the next one", mechanic.pk)
            continue
    raise Conflict("Sorry, that slot just got fully booked. Please pick another time.")
