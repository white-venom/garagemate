"use client";

import { CalendarCheck, CheckCircle2, Home, Loader2, Truck, Warehouse, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, api, errorMessage, type FieldErrors } from "@/lib/api";
import { formatDate, formatPriceRange, toDateInputValue } from "@/lib/format";
import type { Booking, Conversation, Diagnosis, Service, ServiceMode, Slot } from "@/lib/types";

interface BookingModalProps {
  open: boolean;
  onClose: () => void;
  conversation: Conversation | null;
  diagnosis: Diagnosis | null;
  onBooked: (booking: Booking) => void;
}

interface FormState {
  service: string;
  customer_name: string;
  phone: string;
  email: string;
  vehicle_make: string;
  vehicle_model: string;
  vehicle_year: string;
  registration_number: string;
  service_mode: ServiceMode;
  address: string;
  scheduled_date: string;
  time_slot: string;
  notes: string;
}

const SERVICE_MODES: { value: ServiceMode; label: string; hint: string; icon: typeof Home }[] = [
  { value: "garage", label: "Garage visit", hint: "Bring the car to us", icon: Warehouse },
  { value: "doorstep", label: "Doorstep", hint: "Mechanic comes to you", icon: Home },
  { value: "pickup", label: "Pickup & drop", hint: "We collect the car", icon: Truck },
];

// name / phone / address are remembered so repeat bookings are quicker
const SAVED_CUSTOMER_KEY = "garagemate.customer";
const MAX_DAYS_AHEAD = 30;

function readSavedCustomer(): Partial<FormState> {
  try {
    return JSON.parse(localStorage.getItem(SAVED_CUSTOMER_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveCustomer(form: FormState) {
  try {
    const { customer_name, phone, email, address } = form;
    localStorage.setItem(SAVED_CUSTOMER_KEY, JSON.stringify({ customer_name, phone, email, address }));
  } catch {
    // ignore
  }
}

function isSunday(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day).getDay() === 0;
}

function defaultDate() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  if (date.getDay() === 0) date.setDate(date.getDate() + 1);
  return toDateInputValue(date);
}

function validate(form: FormState) {
  const errors: Record<string, string> = {};
  if (form.customer_name.trim().length < 2) errors.customer_name = "Please enter your name.";
  if (!/^\+?\d{10,13}$/.test(form.phone.replace(/[\s\-()]/g, ""))) errors.phone = "Enter a valid phone number.";
  if (form.email && !/^\S+@\S+\.\S+$/.test(form.email)) errors.email = "That email doesn't look right.";
  if (!form.vehicle_make.trim()) errors.vehicle_make = "Which make is the car?";
  if (!form.vehicle_model.trim()) errors.vehicle_model = "Which model?";
  if (form.vehicle_year) {
    const year = Number(form.vehicle_year);
    if (!Number.isInteger(year) || year < 1980 || year > new Date().getFullYear() + 1) errors.vehicle_year = "Check the year.";
  }
  if (!form.scheduled_date) errors.scheduled_date = "Pick a date.";
  else if (isSunday(form.scheduled_date)) errors.scheduled_date = "We're closed on Sundays.";
  if (!form.time_slot) errors.time_slot = "Pick a time slot.";
  if (form.service_mode !== "garage" && form.address.trim().length < 10) {
    errors.address = "We need the full address to send the mechanic.";
  }
  return errors;
}

function flattenFieldErrors(fields: FieldErrors) {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(fields)) {
    result[key] = Array.isArray(value) ? value[0] : value;
  }
  return result;
}

function Field({ label, error, children, optional }: { label: string; error?: string; children: React.ReactNode; optional?: boolean }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-stone-700">
        {label} {optional && <span className="font-normal text-stone-400">(optional)</span>}
      </span>
      <div className="mt-1">{children}</div>
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  );
}

const inputClass =
  "w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-200";

function BookingForm({ onClose, conversation, diagnosis, onBooked }: Omit<BookingModalProps, "open">) {
  const [form, setForm] = useState<FormState>(() => {
    const saved = readSavedCustomer();
    return {
      service: diagnosis?.recommended_service?.code ?? "general-inspection",
      customer_name: saved.customer_name ?? "",
      phone: saved.phone ?? "",
      email: saved.email ?? "",
      vehicle_make: conversation?.vehicle.make ?? "",
      vehicle_model: conversation?.vehicle.model ?? "",
      vehicle_year: conversation?.vehicle.year ? String(conversation.vehicle.year) : "",
      registration_number: "",
      service_mode: "garage",
      address: saved.address ?? "",
      scheduled_date: defaultDate(),
      time_slot: "",
      notes: "",
    };
  });
  const [services, setServices] = useState<Service[]>([]);
  const [slotData, setSlotData] = useState<{ date: string; slots: Slot[]; error?: string } | null>(null);
  const [slotsVersion, setSlotsVersion] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [booking, setBooking] = useState<Booking | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listServices()
      .then((data) => !cancelled && setServices(data.results))
      .catch((error) => !cancelled && setFormError(errorMessage(error)));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!form.scheduled_date) return;
    let cancelled = false;
    const date = form.scheduled_date;
    api
      .getSlots(date)
      .then((data) => !cancelled && setSlotData({ date, slots: data.slots }))
      .catch((error) => !cancelled && setSlotData({ date, slots: [], error: errorMessage(error) }));
    return () => {
      cancelled = true;
    };
  }, [form.scheduled_date, slotsVersion]);

  const slotsLoading = Boolean(form.scheduled_date) && slotData?.date !== form.scheduled_date;
  const selectedService = services.find((service) => service.code === form.service);

  const setField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((previous) => ({ ...previous, [key]: value }));
    setErrors((previous) => {
      if (!previous[key]) return previous;
      const next = { ...previous };
      delete next[key];
      return next;
    });
  };

  const changeDate = (value: string) => {
    setForm((previous) => ({ ...previous, scheduled_date: value, time_slot: "" }));
    setErrors((previous) => ({ ...previous, scheduled_date: value && isSunday(value) ? "We're closed on Sundays." : "" }));
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const clientErrors = validate(form);
    if (Object.keys(clientErrors).length > 0) {
      setErrors(clientErrors);
      setFormError("Please fix the highlighted fields.");
      return;
    }

    setSubmitting(true);
    setErrors({});
    setFormError(null);
    try {
      const created = await api.createBooking({
        ...form,
        vehicle_year: form.vehicle_year ? Number(form.vehicle_year) : null,
        address: form.service_mode === "garage" ? "" : form.address,
        conversation_id: conversation?.id ?? null,
        diagnosis_id: diagnosis?.id ?? null,
      });
      saveCustomer(form);
      setBooking(created);
      onBooked(created);
    } catch (error) {
      if (error instanceof ApiError && error.fields) setErrors(flattenFieldErrors(error.fields));
      if (error instanceof ApiError && error.status === 409) {
        setField("time_slot", "");
        setSlotsVersion((version) => version + 1);
      }
      setFormError(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  const today = new Date();
  const maxDate = new Date();
  maxDate.setDate(today.getDate() + MAX_DAYS_AHEAD);

  if (booking) {
    return (
      <div className="flex flex-col items-center px-6 py-10 text-center">
        <span className="grid size-14 place-items-center rounded-full bg-emerald-100 text-emerald-700">
          <CheckCircle2 className="size-8" />
        </span>
        <h2 className="mt-4 text-xl font-semibold text-stone-900">Mechanic booked</h2>
        <p className="mt-1 text-sm text-stone-600">We&apos;ll call you before the visit to confirm.</p>

        <dl className="mt-6 w-full space-y-2 rounded-xl bg-stone-50 p-4 text-left text-sm ring-1 ring-stone-200">
          <div className="flex justify-between gap-4">
            <dt className="text-stone-500">Reference</dt>
            <dd className="font-mono font-semibold text-stone-900">{booking.reference}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-stone-500">Service</dt>
            <dd className="text-right text-stone-900">{booking.service.name}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-stone-500">When</dt>
            <dd className="text-right text-stone-900">
              {formatDate(booking.scheduled_date)}, {booking.time_slot_label}
            </dd>
          </div>
          {booking.mechanic && (
            <div className="flex justify-between gap-4">
              <dt className="text-stone-500">Mechanic</dt>
              <dd className="text-right text-stone-900">
                {booking.mechanic.name} ({booking.mechanic.experience_years} yrs)
              </dd>
            </div>
          )}
        </dl>

        <div className="mt-6 flex w-full flex-col gap-2 sm:flex-row">
          <Link
            href={`/booking/${booking.id}`}
            className="flex-1 rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50"
          >
            View booking
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-700"
          >
            Back to chat
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={submit} noValidate className="flex max-h-full flex-col">
      <div className="flex items-start justify-between border-b border-stone-200 px-5 py-4">
        <div>
          <h2 id="booking-title" className="text-lg font-semibold text-stone-900">
            Book a mechanic
          </h2>
          <p className="text-sm text-stone-500">
            {diagnosis ? `For: ${diagnosis.title}` : "Pick a service, date and time that suits you."}
          </p>
        </div>
        <button type="button" onClick={onClose} className="rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700" aria-label="Close">
          <X className="size-5" />
        </button>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
        <Field label="Service" error={errors.service}>
          <select value={form.service} onChange={(event) => setField("service", event.target.value)} className={inputClass}>
            {services.length === 0 && <option value={form.service}>Loading services...</option>}
            {services.map((service) => (
              <option key={service.code} value={service.code}>
                {service.name}
              </option>
            ))}
          </select>
          {selectedService && (
            <p className="mt-1 text-xs text-stone-500">
              {formatPriceRange(selectedService.price_min, selectedService.price_max)} · about{" "}
              {Math.round(selectedService.duration_minutes / 30) / 2} hr
            </p>
          )}
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Your name" error={errors.customer_name}>
            <input value={form.customer_name} onChange={(event) => setField("customer_name", event.target.value)} className={inputClass} autoComplete="name" autoFocus />
          </Field>
          <Field label="Phone" error={errors.phone}>
            <input value={form.phone} onChange={(event) => setField("phone", event.target.value)} className={inputClass} inputMode="tel" autoComplete="tel" placeholder="98765 43210" />
          </Field>
        </div>

        <Field label="Email" optional error={errors.email}>
          <input type="email" value={form.email} onChange={(event) => setField("email", event.target.value)} className={inputClass} autoComplete="email" />
        </Field>

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="col-span-1 sm:col-span-1">
            <Field label="Make" error={errors.vehicle_make}>
              <input value={form.vehicle_make} onChange={(event) => setField("vehicle_make", event.target.value)} className={inputClass} placeholder="Hyundai" />
            </Field>
          </div>
          <div className="col-span-1 sm:col-span-1">
            <Field label="Model" error={errors.vehicle_model}>
              <input value={form.vehicle_model} onChange={(event) => setField("vehicle_model", event.target.value)} className={inputClass} placeholder="Creta" />
            </Field>
          </div>
          <Field label="Year" optional error={errors.vehicle_year}>
            <input value={form.vehicle_year} onChange={(event) => setField("vehicle_year", event.target.value)} className={inputClass} inputMode="numeric" maxLength={4} placeholder="2019" />
          </Field>
          <Field label="Reg. no." optional error={errors.registration_number}>
            <input
              value={form.registration_number}
              onChange={(event) => setField("registration_number", event.target.value.toUpperCase())}
              className={inputClass}
              placeholder="MH12AB1234"
              maxLength={15}
            />
          </Field>
        </div>

        <fieldset>
          <legend className="text-sm font-medium text-stone-700">Where should we look at the car?</legend>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
            {SERVICE_MODES.map(({ value, label, hint, icon: Icon }) => (
              <label
                key={value}
                className={`flex cursor-pointer items-start gap-2 rounded-xl border p-3 text-sm transition ${
                  form.service_mode === value ? "border-amber-400 bg-amber-50 ring-1 ring-amber-300" : "border-stone-200 hover:bg-stone-50"
                }`}
              >
                <input type="radio" name="service_mode" value={value} checked={form.service_mode === value} onChange={() => setField("service_mode", value)} className="sr-only" />
                <Icon className="mt-0.5 size-4 shrink-0 text-stone-600" />
                <span>
                  <span className="block font-medium text-stone-900">{label}</span>
                  <span className="text-xs text-stone-500">{hint}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        {form.service_mode !== "garage" && (
          <Field label="Address" error={errors.address}>
            <textarea
              value={form.address}
              onChange={(event) => setField("address", event.target.value)}
              className={`${inputClass} min-h-20`}
              placeholder="House / flat, street, area, city, pincode"
              autoComplete="street-address"
            />
          </Field>
        )}

        <Field label="Date" error={errors.scheduled_date}>
          <input
            type="date"
            value={form.scheduled_date}
            min={toDateInputValue(today)}
            max={toDateInputValue(maxDate)}
            onChange={(event) => changeDate(event.target.value)}
            className={inputClass}
          />
        </Field>

        <div>
          <p className="text-sm font-medium text-stone-700">Time slot</p>
          {slotsLoading ? (
            <p className="mt-2 flex items-center gap-2 text-sm text-stone-500">
              <Loader2 className="size-4 animate-spin" /> Checking availability...
            </p>
          ) : slotData?.error ? (
            <p className="mt-2 text-sm text-red-600">{slotData.error}</p>
          ) : (
            <div className="mt-2 grid grid-cols-2 gap-2">
              {slotData?.slots.map((slot) => (
                <button
                  key={slot.value}
                  type="button"
                  disabled={!slot.available}
                  onClick={() => setField("time_slot", slot.value)}
                  className={`rounded-lg border px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed disabled:opacity-40 ${
                    form.time_slot === slot.value ? "border-amber-400 bg-amber-50 ring-1 ring-amber-300" : "border-stone-200 hover:bg-stone-50"
                  }`}
                >
                  <span className="block font-medium text-stone-900">{slot.label}</span>
                  <span className="text-xs text-stone-500">
                    {slot.available ? `${slot.remaining} mechanic${slot.remaining === 1 ? "" : "s"} free` : "Not available"}
                  </span>
                </button>
              ))}
            </div>
          )}
          {errors.time_slot && <span className="mt-1 block text-xs text-red-600">{errors.time_slot}</span>}
        </div>

        <Field label="Anything else the mechanic should know?" optional error={errors.notes}>
          <textarea value={form.notes} onChange={(event) => setField("notes", event.target.value)} className={`${inputClass} min-h-16`} maxLength={1000} />
        </Field>
      </div>

      <div className="border-t border-stone-200 px-5 py-4">
        {formError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{formError}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 text-sm font-semibold text-stone-900 transition hover:bg-amber-400 disabled:opacity-60"
        >
          {submitting ? <Loader2 className="size-4 animate-spin" /> : <CalendarCheck className="size-4" />}
          {submitting ? "Booking..." : "Confirm booking"}
        </button>
      </div>
    </form>
  );
}

export default function BookingModal({ open, ...props }: BookingModalProps) {
  const { onClose } = props;

  useEffect(() => {
    if (!open) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="booking-title"
        onClick={(event) => event.stopPropagation()}
        className="flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-2xl bg-white shadow-xl sm:max-w-xl sm:rounded-2xl"
      >
        {/* remounted every time it opens so the form starts fresh from the latest diagnosis */}
        <BookingForm {...props} />
      </div>
    </div>
  );
}
