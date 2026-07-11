"use client";

import { useMemo, useState } from "react";

const LABELS = {
  verified: { mark: "✅", text: "Verified" },
  likely: { mark: "🟡", text: "Likely — call ahead" },
  unverified: { mark: "❓", text: "Unverified" },
};

const SOURCE_NAMES = {
  venue_website: "Venue website",
  google_review: "Google review",
  google_allows_dogs: "Google venue flag",
  sample_allows_dogs: "Venue flag",
  review_keyword: "Review",
};

function haversineKm(lat1, lng1, lat2, lng2) {
  const r = (d) => (d * Math.PI) / 180;
  const a =
    Math.sin(r(lat2 - lat1) / 2) ** 2 +
    Math.cos(r(lat1)) * Math.cos(r(lat2)) * Math.sin(r(lng2 - lng1) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(a));
}

function PolicyChips({ policy }) {
  if (!policy || Object.keys(policy).length === 0) return null;
  const chips = [];
  if (policy.seating === "both") chips.push("🪑 indoor + outdoor");
  else if (policy.seating === "indoor") chips.push("🪑 indoor OK");
  else if (policy.seating === "outdoor_only") chips.push("🌳 outdoor only");
  if (policy.pet_sizes) chips.push(`📏 ${policy.pet_sizes}`);
  if (policy.fee) chips.push(`💰 ${policy.fee}`);
  for (const a of policy.amenities || []) chips.push(`✨ ${a}`);
  if (chips.length === 0 && (policy.pet_types || []).length)
    chips.push(`🐾 ${policy.pet_types.join(", ")}`);
  return (
    <div className="chips">
      {chips.map((c) => (
        <span key={c} className="chip">
          {c}
        </span>
      ))}
    </div>
  );
}

function PlaceCard({ place, distanceKm }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const label = LABELS[place.label] || LABELS.unverified;

  return (
    <article className={`card ${place.label}`}>
      <div className="card-head">
        <div>
          <h2>{place.name}</h2>
          <p className="sub">
            {[place.category, place.city].filter(Boolean).join(" · ")}
            {place.rating ? ` · ${place.rating}★` : ""}
            {distanceKm != null ? ` · ${distanceKm.toFixed(1)} km away` : ""}
          </p>
        </div>
        <div className={`badge badge-${place.label}`} title={label.text}>
          {label.mark} {label.text}
        </div>
      </div>

      <PolicyChips policy={place.policy} />

      <div className="card-actions">
        {place.phone && <a href={`tel:${place.phone}`}>📞 {place.phone}</a>}
        {place.website && (
          <a href={place.website} target="_blank" rel="noopener noreferrer">
            🔗 Website
          </a>
        )}
        {place.lat != null && (
          <a
            href={`https://www.google.com/maps/search/?api=1&query=${place.lat},${place.lng}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            🗺️ Map
          </a>
        )}
        {place.evidence.length > 0 && (
          <button onClick={() => setShowEvidence(!showEvidence)}>
            {showEvidence ? "Hide evidence" : `Why we believe this (${place.evidence.length})`}
          </button>
        )}
      </div>

      {showEvidence && (
        <ul className="evidence">
          {place.evidence.map((e, i) => (
            <li key={i} className={e.polarity}>
              <span className="pol">{e.polarity === "positive" ? "✓" : "✗"}</span>{" "}
              {e.claim}{" "}
              <span className="prov">
                — {SOURCE_NAMES[e.source] || e.source}
                {e.date ? `, ${e.date}` : ""}
                {e.url && (
                  <>
                    {" "}
                    <a href={e.url} target="_blank" rel="noopener noreferrer">
                      source
                    </a>
                  </>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

export default function Directory({ places }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [city, setCity] = useState("all");
  const [evidencedOnly, setEvidencedOnly] = useState(true);
  const [origin, setOrigin] = useState(null);
  const [locating, setLocating] = useState(false);

  const cities = useMemo(
    () => [...new Set(places.map((p) => p.city).filter(Boolean))].sort(),
    [places],
  );
  const categories = useMemo(
    () => [...new Set(places.map((p) => p.category).filter(Boolean))].sort(),
    [places],
  );

  const locate = () => {
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setOrigin({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocating(false);
      },
      () => setLocating(false),
      { timeout: 10000 },
    );
  };

  const visible = useMemo(() => {
    let list = places.filter((p) => {
      if (query && !p.name.toLowerCase().includes(query.toLowerCase())) return false;
      if (category !== "all" && p.category !== category) return false;
      if (city !== "all" && p.city !== city) return false;
      if (evidencedOnly && p.evidence.length === 0) return false;
      return true;
    });
    if (origin) {
      list = list
        .map((p) => ({
          ...p,
          _km:
            p.lat != null
              ? haversineKm(origin.lat, origin.lng, p.lat, p.lng)
              : Infinity,
        }))
        .sort((a, b) => a._km - b._km);
    }
    return list;
  }, [places, query, category, city, evidencedOnly, origin]);

  return (
    <section>
      <div className="controls">
        <input
          type="search"
          placeholder="Search places…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="all">All types</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select value={city} onChange={(e) => setCity(e.target.value)}>
          <option value="all">All cities</option>
          {cities.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <label className="toggle">
          <input
            type="checkbox"
            checked={evidencedOnly}
            onChange={(e) => setEvidencedOnly(e.target.checked)}
          />
          With pet evidence only
        </label>
        <button onClick={locate} disabled={locating || !!origin}>
          {origin ? "📍 Sorted by distance" : locating ? "Locating…" : "📍 Near me"}
        </button>
      </div>

      <p className="count">{visible.length} places</p>

      <div className="grid">
        {visible.map((p) => (
          <PlaceCard key={p.id} place={p} distanceKm={origin ? p._km : null} />
        ))}
      </div>
    </section>
  );
}
