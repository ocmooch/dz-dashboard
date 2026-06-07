import { useEffect, useId, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { api } from "@/lib/api/client";
import { qk } from "@/lib/queryKeys";

type Hit = {
  type: string;
  id: number;
  label: string;
  sublabel?: string | null;
  href: string;
};

async function fetchSearch(q: string): Promise<Hit[]> {
  const { data, error } = await api.GET("/v1/search", {
    params: { query: { q, limit: 25 } },
  });
  if (error || !data) throw new Error("Search failed");
  return data.data.hits as Hit[];
}

const TYPE_GLYPH: Record<string, string> = { owner: "◆", season: "▦", player: "●" };

/** Small debounce so typeahead doesn't fire a request per keystroke. */
function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

/** Global typeahead: queries /v1/search and navigates to the chosen entity.
 *  Replaces the P-pre-10 placeholder. `/` focuses it from anywhere; arrows +
 *  Enter pick a hit; Escape closes. Season hits also switch the season context,
 *  since their deep-link is the shared /standings view. */
export function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const debounced = useDebounced(query.trim(), 150);
  const navigate = useNavigate();
  const { setSeasonId } = useSeasons();
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const enabled = debounced.length > 0;
  const { data: hits = [], isFetching } = useQuery({
    queryKey: qk.search(debounced),
    queryFn: () => fetchSearch(debounced),
    enabled,
    staleTime: 30_000,
  });

  // "/" focuses search from anywhere it isn't already an input target.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/") return;
      const el = document.activeElement;
      const typing =
        el instanceof HTMLInputElement ||
        el instanceof HTMLTextAreaElement ||
        el instanceof HTMLSelectElement ||
        (el instanceof HTMLElement && el.isContentEditable);
      if (typing) return;
      e.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Close when focus/clicks leave the widget.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  // Keep the active index in range as the result set changes.
  useEffect(() => setActive(0), [debounced]);

  const showMenu = open && enabled;

  function choose(hit: Hit) {
    if (hit.type === "season") setSeasonId(hit.id);
    setOpen(false);
    setQuery("");
    inputRef.current?.blur();
    navigate(hit.href);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
      return;
    }
    if (!showMenu || hits.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (a + 1) % hits.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (a - 1 + hits.length) % hits.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const hit = hits[active];
      if (hit) choose(hit);
    }
  }

  return (
    <div ref={rootRef} className="dz-search-wrap">
      <div className="dz-search dz-search--live">
        <span aria-hidden>⌕</span>
        <input
          ref={inputRef}
          type="search"
          className="dz-search-input"
          placeholder="Search managers, players, seasons…"
          aria-label="Global search"
          role="combobox"
          aria-expanded={showMenu}
          aria-controls={listId}
          aria-autocomplete="list"
          autoComplete="off"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
        />
        {!query && <kbd>/</kbd>}
      </div>

      {showMenu && (
        <ul className="dz-search-menu" id={listId} role="listbox" aria-label="Search results">
          {hits.length === 0 ? (
            <li className="dz-search-empty" role="presentation">
              {isFetching ? "Searching…" : `No matches for “${debounced}”`}
            </li>
          ) : (
            hits.map((hit, i) => (
              <li
                key={`${hit.type}-${hit.id}`}
                role="option"
                aria-selected={i === active}
                className={`dz-search-hit ${i === active ? "is-active" : ""}`.trim()}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => {
                  // mousedown (not click) so we fire before the input blurs the menu shut.
                  e.preventDefault();
                  choose(hit);
                }}
              >
                <span className="dz-search-glyph" aria-hidden>
                  {TYPE_GLYPH[hit.type] ?? "•"}
                </span>
                <span className="dz-search-hit-label">{hit.label}</span>
                {hit.sublabel && <span className="dz-search-hit-sub">{hit.sublabel}</span>}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
