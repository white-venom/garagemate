"use client";

import { ArrowLeft, CalendarDays, Car, Loader2, MapPin, UserRound, Wrench } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { formatDate, formatPriceRange } from "@/lib/format";
import type { Booking, BookingStatus } from "@/lib/types";

const statusStyles: Record<BookingStatus, string> = {
  confirmed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  completed: "bg-sky-50 text-sky-700 ring-sky-200",
  cancelled: "bg-stone-100 text-stone-600 ring-stone-300",
};

function Row({ icon: Icon, label, children }: { icon: typeof Car; label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 py-3">
      <Icon className="mt-0.5 size-4 shrink-0 text-stone-400" />
      <div className="min-w-0 flex-1">
        <p className="text-xs uppercase tracking-wide text-stone-500">{label}</p>
        <div className="mt-0.5 text-sm text-stone-900">{children}</div>
      </div>
    </div>
  );
}

export default function BookingDetails({ id }: { id: string }) {
  const [booking, setBooking] = useState<Booking | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getBooking(id)
      .then((data) => !cancelled && setBooking(data))
      .catch((err) => !cancelled && setError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [id]);

  const cancelBooking = async () => {
    if (!booking || !window.confirm("Cancel this booking?")) return;
    setCancelling(true);
    try {
      setBooking(await api.cancelBooking(booking.id));
    } catch (err) {
      window.alert(errorMessage(err));
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="min-h-full bg-stone-100 px-4 py-8 sm:py-12">
      <div className="mx-auto max-w-lg">
        <Link href="/" className="inline-flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-900">
          <ArrowLeft className="size-4" /> Back to chat
        </Link>

        {!booking && !error && (
          <div className="mt-10 flex justify-center text-stone-500">
            <Loader2 className="size-6 animate-spin" />
          </div>
        )}

        {error && (
          <div className="mt-6 rounded-2xl bg-white p-6 text-center shadow-sm ring-1 ring-stone-200">
            <p className="font-medium text-stone-900">Couldn&apos;t load this booking</p>
            <p className="mt-1 text-sm text-stone-600">{error}</p>
          </div>
        )}

        {booking && (
          <article className="mt-6 overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-stone-200">
            <header className="bg-stone-900 px-5 py-5 text-white">
              <p className="text-xs uppercase tracking-wide text-stone-400">Booking reference</p>
              <div className="mt-1 flex items-center justify-between gap-3">
                <h1 className="font-mono text-2xl font-semibold">{booking.reference}</h1>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${statusStyles[booking.status]}`}>
                  {booking.status_label}
                </span>
              </div>
            </header>

            <div className="divide-y divide-stone-100 px-5">
              <Row icon={Wrench} label="Service">
                {booking.service.name}
                <p className="text-xs text-stone-500">
                  {formatPriceRange(booking.service.price_min, booking.service.price_max)}, final price after inspection
                </p>
              </Row>
              <Row icon={CalendarDays} label="When">
                {formatDate(booking.scheduled_date)}, {booking.time_slot_label}
              </Row>
              <Row icon={MapPin} label="Where">
                {booking.service_mode_label}
                {booking.address && <p className="text-xs text-stone-500">{booking.address}</p>}
              </Row>
              <Row icon={Car} label="Vehicle">
                {[booking.vehicle_year, booking.vehicle_make, booking.vehicle_model].filter(Boolean).join(" ")}
                {booking.registration_number && <span className="text-stone-500"> · {booking.registration_number}</span>}
              </Row>
              <Row icon={UserRound} label="Mechanic">
                {booking.mechanic ? (
                  <>
                    {booking.mechanic.name}
                    <p className="text-xs text-stone-500">
                      {booking.mechanic.speciality}, {booking.mechanic.experience_years} years experience
                    </p>
                  </>
                ) : (
                  "Will be assigned shortly"
                )}
              </Row>
              {booking.notes && (
                <Row icon={Wrench} label="Notes">
                  <p className="whitespace-pre-wrap">{booking.notes}</p>
                </Row>
              )}
            </div>

            <footer className="flex flex-col gap-2 border-t border-stone-100 px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between">
              <p className="text-stone-500">
                Booked for {booking.customer_name} ({booking.phone})
              </p>
              {booking.can_cancel && (
                <button
                  type="button"
                  onClick={cancelBooking}
                  disabled={cancelling}
                  className="rounded-lg border border-red-200 px-3 py-1.5 font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                >
                  {cancelling ? "Cancelling..." : "Cancel booking"}
                </button>
              )}
            </footer>
          </article>
        )}
      </div>
    </div>
  );
}
