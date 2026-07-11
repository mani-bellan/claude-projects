import fs from "node:fs/promises";
import path from "node:path";
import Directory from "./components/Directory";

export default async function Home() {
  const file = path.join(process.cwd(), "public", "data", "places.json");
  const snapshot = JSON.parse(await fs.readFile(file, "utf8"));

  return (
    <main>
      <header className="hero">
        <h1>
          Paw<span>Spots</span>
        </h1>
        <p className="tagline">
          Pet-friendly cafes, restaurants &amp; stays across India — every
          listing backed by evidence, not hearsay.
        </p>
        <p className="meta">
          {snapshot.place_count} places · data refreshed{" "}
          {snapshot.generated_at.slice(0, 10)}
        </p>
      </header>
      <Directory places={snapshot.places} />
      <footer>
        <p>
          Labels: ✅ verified (multiple corroborating sources) · 🟡 likely
          (good evidence — call ahead) · ❓ unverified (insufficient evidence).
          Policies change; the badge date tells you how fresh our evidence is.
        </p>
      </footer>
    </main>
  );
}
