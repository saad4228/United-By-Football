import { COUNTRY_CODES, countryName, useCountry } from "../lib/country";
import { GlobeIcon } from "./Icons";

/** "Watching from: India ▾" — sources are ordered and filtered for this country. */
export function CountryPicker({ className = "" }: { className?: string }) {
  const { country, setCountry } = useCountry();
  const codes = country && !COUNTRY_CODES.includes(country) ? [country, ...COUNTRY_CODES] : COUNTRY_CODES;
  const options = [...codes].sort((a, b) => countryName(a).localeCompare(countryName(b)));
  return (
    <label className={`inline-flex items-center gap-2 text-[15px] text-fg-2 ${className}`}>
      <GlobeIcon size={16} className="text-faint" />
      <span className="text-faint">Watching from</span>
      <select
        value={country ?? ""}
        onChange={(e) => e.target.value && setCountry(e.target.value)}
        className="h-9 rounded-lg border border-line bg-surface px-2.5 font-semibold text-fg outline-none hover:border-line-strong"
        aria-label="Your country"
      >
        {!country && <option value="">Choose country</option>}
        {options.map((code) => (
          <option key={code} value={code}>
            {countryName(code)}
          </option>
        ))}
      </select>
    </label>
  );
}
