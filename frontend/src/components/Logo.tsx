// gauge mark, same drawing as app/icon.svg
export default function Logo({ className = "size-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="9" className="fill-brand-500" />
      <path d="M7.5 21a8.5 8.5 0 1 1 17 0" fill="none" stroke="#121418" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M16 21l5-6" stroke="#121418" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="16" cy="21" r="2.3" fill="#121418" />
    </svg>
  );
}
