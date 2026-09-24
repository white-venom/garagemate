"use client";

import { Car as CarIcon, Loader2, Plus, Star, Trash2, UserRound, X } from "lucide-react";
import { useEffect, useState } from "react";

import { ApiError, api, errorMessage } from "@/lib/api";
import { formatPlate } from "@/lib/format";
import type { Car, Profile } from "@/lib/types";

import { NumberPlate } from "./ChatHeader";

interface ProfileModalProps {
  open: boolean;
  onClose: () => void;
  profile: Profile | null;
  onChange: (profile: Profile) => void;
  // opened by itself on the first visit: one save button for everything and a way to skip
  welcome?: boolean;
}

const FUELS = [
  { value: "", label: "Fuel" },
  { value: "petrol", label: "Petrol" },
  { value: "diesel", label: "Diesel" },
  { value: "cng", label: "CNG" },
  { value: "electric", label: "Electric" },
  { value: "hybrid", label: "Hybrid" },
];

const EMPTY_CAR = { make: "", model: "", year: "", fuel_type: "", odometer_km: "", registration_number: "" };

const inputClass =
  "w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-ink-900 outline-none transition placeholder:text-stone-400 focus:border-brand-400 focus:ring-4 focus:ring-brand-100";

function firstError(error: unknown) {
  if (error instanceof ApiError && error.fields) {
    const value = Object.values(error.fields)[0];
    return Array.isArray(value) ? value[0] : value;
  }
  return errorMessage(error);
}

function CarRow({ car, onChanged, onError }: { car: Car; onChanged: () => Promise<void>; onError: (message: string) => void }) {
  const [busy, setBusy] = useState(false);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await action();
      await onChanged();
    } catch (error) {
      onError(firstError(error));
    } finally {
      setBusy(false);
    }
  };

  const details = [
    car.fuel_type && car.fuel_type[0].toUpperCase() + car.fuel_type.slice(1),
    car.odometer_km ? `${car.odometer_km.toLocaleString("en-IN")} km` : "",
    car.registration_number && formatPlate(car.registration_number),
  ].filter(Boolean);

  return (
    <li className="flex items-center gap-3 rounded-xl border border-stone-200 bg-white p-3">
      <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${car.is_primary ? "bg-brand-500 text-ink-950" : "bg-stone-100 text-stone-500"}`}>
        <CarIcon className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 truncate text-sm font-semibold text-ink-900">
          {car.label}
          {car.is_primary && (
            <span className="rounded-full bg-brand-50 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-brand-700">Primary</span>
          )}
        </p>
        <p className="truncate text-xs text-stone-500">{details.join(" · ") || "No extra details"}</p>
      </div>
      {busy ? (
        <Loader2 className="size-4 animate-spin text-stone-400" />
      ) : (
        <div className="flex gap-1">
          {!car.is_primary && (
            <button
              type="button"
              onClick={() => run(() => api.updateCar(car.id, { is_primary: true }))}
              className="rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-brand-600"
              title="Make primary"
              aria-label={`Make ${car.label} the primary car`}
            >
              <Star className="size-4" />
            </button>
          )}
          <button
            type="button"
            onClick={() => window.confirm(`Remove ${car.label}?`) && run(() => api.deleteCar(car.id))}
            className="rounded-md p-1.5 text-stone-400 hover:bg-red-50 hover:text-red-600"
            aria-label={`Remove ${car.label}`}
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      )}
    </li>
  );
}

function ProfileForm({ onClose, profile, onChange, welcome = false }: Omit<ProfileModalProps, "open">) {
  const [about, setAbout] = useState({
    name: profile?.name ?? "",
    phone: profile?.phone ?? "",
    email: profile?.email ?? "",
    city: profile?.city ?? "",
  });
  const [car, setCar] = useState(EMPTY_CAR);
  const [addingCar, setAddingCar] = useState(!profile?.cars.length);
  const [saving, setSaving] = useState<"about" | "car" | "all" | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const cars = profile?.cars ?? [];

  const refresh = async () => {
    onChange(await api.getProfile());
  };

  const saveAbout = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving("about");
    setMessage(null);
    try {
      onChange(await api.updateProfile(about));
      setMessage({ tone: "ok", text: "Saved. I'll use this to personalise the chat and prefill bookings." });
    } catch (error) {
      setMessage({ tone: "error", text: firstError(error) });
    } finally {
      setSaving(null);
    }
  };

  const addTypedCar = () =>
    api.addCar({
      make: car.make,
      model: car.model,
      year: car.year ? Number(car.year) : null,
      fuel_type: car.fuel_type,
      odometer_km: car.odometer_km ? Number(car.odometer_km.replace(/[^\d]/g, "")) : null,
      registration_number: car.registration_number,
    });

  const saveCar = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!car.make.trim() || !car.model.trim()) {
      setMessage({ tone: "error", text: "Add at least the make and model." });
      return;
    }
    setSaving("car");
    setMessage(null);
    try {
      await addTypedCar();
      await refresh();
      setCar(EMPTY_CAR);
      setAddingCar(false);
    } catch (error) {
      setMessage({ tone: "error", text: firstError(error) });
    } finally {
      setSaving(null);
    }
  };

  const saveAndStart = async () => {
    const carTyped = addingCar && Boolean(car.make.trim() || car.model.trim());
    if (!about.name.trim()) {
      setMessage({ tone: "error", text: "Tell me your name so I know what to call you." });
      return;
    }
    if ((!cars.length || carTyped) && !(car.make.trim() && car.model.trim())) {
      setMessage({ tone: "error", text: "Add your car's make and model, e.g. Maruti Swift." });
      return;
    }
    setSaving("all");
    setMessage(null);
    try {
      onChange(await api.updateProfile(about));
      if (carTyped) {
        await addTypedCar();
        await refresh();
      }
      onClose();
    } catch (error) {
      setMessage({ tone: "error", text: firstError(error) });
      setSaving(null);
    }
  };

  const primary = cars.find((item) => item.is_primary);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="relative overflow-hidden bg-ink-900 px-5 pb-5 pt-5 text-white">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-brand-400">
              {welcome ? "Before we start" : "My garage"}
            </p>
            <h2 id="profile-title" className="mt-1.5 font-display text-xl font-semibold tracking-tight">
              {profile?.name ? `${profile.name.split(" ")[0]}'s garage` : "Tell me about you and your car"}
            </h2>
            <p className="mt-1 max-w-sm text-xs leading-relaxed text-stone-400">
              Saved only for this browser. The mechanic bot greets you by name, asks &quot;is this about your car?&quot;
              instead of making you type it, and bookings get filled in for you.
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-stone-400 hover:bg-white/10 hover:text-white" aria-label="Close">
            <X className="size-5" />
          </button>
        </div>
        {primary && (
          <div className="mt-4">
            <NumberPlate label={primary.registration_number ? formatPlate(primary.registration_number) : primary.label} />
          </div>
        )}
      </header>

      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-contain px-5 py-5">
        {message && (
          <p className={`rounded-lg px-3 py-2 text-sm ${message.tone === "ok" ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-700"}`}>
            {message.text}
          </p>
        )}

        <form onSubmit={saveAbout}>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-900">
            <UserRound className="size-4 text-stone-400" /> About you
          </h3>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <input className={inputClass} placeholder="Your name" value={about.name} onChange={(event) => setAbout({ ...about, name: event.target.value })} autoComplete="name" />
            <input className={inputClass} placeholder="Phone" inputMode="tel" value={about.phone} onChange={(event) => setAbout({ ...about, phone: event.target.value })} autoComplete="tel" />
            <input className={inputClass} placeholder="Email (optional)" type="email" value={about.email} onChange={(event) => setAbout({ ...about, email: event.target.value })} autoComplete="email" />
            <input className={inputClass} placeholder="City (optional)" value={about.city} onChange={(event) => setAbout({ ...about, city: event.target.value })} autoComplete="address-level2" />
          </div>
          {!welcome && (
            <button
              type="submit"
              disabled={saving === "about"}
              className="mt-3 inline-flex items-center gap-2 rounded-lg bg-ink-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-ink-700 disabled:opacity-50"
            >
              {saving === "about" && <Loader2 className="size-4 animate-spin" />} Save details
            </button>
          )}
        </form>

        <section>
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-900">
              <CarIcon className="size-4 text-stone-400" /> My cars
            </h3>
            {!addingCar && cars.length < 5 && (
              <button type="button" onClick={() => setAddingCar(true)} className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:text-brand-800">
                <Plus className="size-4" /> Add car
              </button>
            )}
          </div>

          {cars.length > 0 && (
            <ul className="mt-3 space-y-2">
              {cars.map((item) => (
                <CarRow key={item.id} car={item} onChanged={refresh} onError={(text) => setMessage({ tone: "error", text })} />
              ))}
            </ul>
          )}

          {addingCar && (
            <form onSubmit={saveCar} className="mt-3 rounded-xl border border-dashed border-stone-300 bg-stone-50/60 p-3">
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                <input className={inputClass} placeholder="Make (Maruti)" value={car.make} onChange={(event) => setCar({ ...car, make: event.target.value })} />
                <input className={inputClass} placeholder="Model (Swift)" value={car.model} onChange={(event) => setCar({ ...car, model: event.target.value })} />
                <input className={inputClass} placeholder="Year" inputMode="numeric" maxLength={4} value={car.year} onChange={(event) => setCar({ ...car, year: event.target.value })} />
                <select className={inputClass} value={car.fuel_type} onChange={(event) => setCar({ ...car, fuel_type: event.target.value })}>
                  {FUELS.map((fuel) => (
                    <option key={fuel.value} value={fuel.value}>
                      {fuel.label}
                    </option>
                  ))}
                </select>
                <input className={inputClass} placeholder="Km driven" inputMode="numeric" value={car.odometer_km} onChange={(event) => setCar({ ...car, odometer_km: event.target.value })} />
                <input
                  className={inputClass}
                  placeholder="Reg. no."
                  maxLength={15}
                  value={car.registration_number}
                  onChange={(event) => setCar({ ...car, registration_number: event.target.value.toUpperCase() })}
                />
              </div>
              <div className={`mt-3 flex gap-2 ${welcome && !cars.length ? "hidden" : ""}`}>
                <button
                  type="submit"
                  disabled={saving === "car"}
                  className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-ink-950 transition hover:bg-brand-400 disabled:opacity-50"
                >
                  {saving === "car" && <Loader2 className="size-4 animate-spin" />} Save car
                </button>
                {cars.length > 0 && (
                  <button type="button" onClick={() => setAddingCar(false)} className="rounded-lg px-3 py-2 text-sm text-stone-600 hover:bg-stone-100">
                    Cancel
                  </button>
                )}
              </div>
            </form>
          )}
        </section>
      </div>

      {welcome && (
        <div className="flex items-center justify-between gap-3 border-t border-stone-200 bg-stone-50/70 px-5 py-4">
          <button type="button" onClick={onClose} className="rounded-lg px-3 py-2 text-sm font-medium text-stone-600 hover:bg-stone-100">
            Skip for now
          </button>
          <button
            type="button"
            onClick={saveAndStart}
            disabled={saving !== null}
            className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-ink-950 shadow-[0_8px_20px_-10px] shadow-brand-600 transition hover:bg-brand-400 disabled:opacity-60"
          >
            {saving === "all" && <Loader2 className="size-4 animate-spin" />} Save &amp; start chatting
          </button>
        </div>
      )}
    </div>
  );
}

export default function ProfileModal({ open, ...props }: ProfileModalProps) {
  const { onClose } = props;

  useEffect(() => {
    if (!open) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 backdrop-blur-[1px] sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="profile-title"
        onClick={(event) => event.stopPropagation()}
        className="flex max-h-[92dvh] w-full animate-rise flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:max-w-lg sm:rounded-2xl"
      >
        <ProfileForm {...props} />
      </div>
    </div>
  );
}
