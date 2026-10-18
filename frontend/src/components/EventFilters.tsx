import type { EventType } from "../types/api";

export const ALL_TYPES: EventType[] = ["run.started", "span", "exception", "run.finished"];

export interface FilterState {
  types: EventType[];
  errorsOnly: boolean;
  search: string;
}

export const DEFAULT_FILTERS: FilterState = { types: ALL_TYPES, errorsOnly: false, search: "" };

export function isFiltered(filters: FilterState): boolean {
  return filters.types.length !== ALL_TYPES.length || filters.errorsOnly || filters.search.trim() !== "";
}

export function EventFilters({ value, onChange }: { value: FilterState; onChange: (next: FilterState) => void }) {
  const toggleType = (type: EventType) => {
    const types = value.types.includes(type) ? value.types.filter((t) => t !== type) : [...value.types, type];
    onChange({ ...value, types: ALL_TYPES.filter((t) => types.includes(t)) });
  };

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
      <fieldset className="flex flex-wrap items-center gap-1">
        <legend className="sr-only">Event types</legend>
        {ALL_TYPES.map((type) => {
          const active = value.types.includes(type);
          return (
            <button
              key={type}
              type="button"
              aria-pressed={active}
              onClick={() => toggleType(type)}
              className={`rounded-md border px-2 py-0.5 font-mono text-xs ${
                active ? "border-ink bg-ink text-panel" : "border-line bg-panel text-muted hover:text-ink"
              }`}
            >
              {type}
            </button>
          );
        })}
      </fieldset>
      <label className="flex items-center gap-1.5">
        <input
          type="checkbox"
          checked={value.errorsOnly}
          onChange={(e) => onChange({ ...value, errorsOnly: e.target.checked })}
          className="accent-fault"
        />
        Errors only
      </label>
      <label className="flex items-center gap-1.5">
        <span className="sr-only">Search operations</span>
        <input
          type="search"
          value={value.search}
          onChange={(e) => onChange({ ...value, search: e.target.value })}
          placeholder="Search operations"
          className="w-48 rounded-md border border-line bg-panel px-2 py-1 font-mono text-xs placeholder:font-sans placeholder:text-muted"
        />
      </label>
    </div>
  );
}
