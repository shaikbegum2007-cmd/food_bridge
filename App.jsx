import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity, ArrowDownToLine, ArrowRight, BadgeCheck, Bell, Bike, Check, CheckCircle2,
  ChevronDown, Clock3, Compass, HandHeart, HeartHandshake, Leaf, LogOut, MapPin,
  Menu, PackageCheck, Plus, Search, ShieldCheck, Sparkles, UtensilsCrossed, X,
} from "lucide-react";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, errorMessage } from "./api";

const categories = ["prepared meals", "produce", "bakery", "dairy", "packaged"];
const roleTitles = { donor: "Food donor", ngo: "NGO partner", volunteer: "Volunteer", admin: "Administrator" };
const navByRole = {
  donor: [["Overview", Activity], ["My donations", UtensilsCrossed], ["Smart matches", Sparkles], ["Deliveries", Bike]],
  ngo: [["Overview", Activity], ["Nearby food", Compass], ["Deliveries", Bike], ["Organization profile", BadgeCheck]],
  volunteer: [["Overview", Activity], ["My tasks", Bike], ["My profile", BadgeCheck]],
  admin: [["Overview", Activity], ["Deliveries", Bike], ["NGO verification", ShieldCheck], ["Volunteer management", HandHeart], ["People", HandHeart], ["Food safety", HeartHandshake]],
};
const emptyDonation = {
  title: "", category: "prepared meals", quantity_servings: 20,
  prepared_at: "", pickup_deadline: "", storage_method: "", allergens: "Not specified",
  packaging_condition: "Sealed, food-safe containers", pickup_address: "", latitude: "", longitude: "", photo_url: "",
};
const emptyProfile = { service_area: "", accepted_categories: ["prepared meals", "produce", "bakery", "dairy", "packaged"], receiving_capacity: 100, latitude: "", longitude: "" };

function Logo({ small = false }) {
  return <div className={`brand ${small ? "brand-small" : ""}`}><span className="brand-icon"><Leaf size={18} strokeWidth={2.2} /></span><span>FoodBridge</span></div>;
}

function Field({ label, children, className = "" }) {
  return <label className={`field ${className}`}><span>{label}</span>{children}</label>;
}

function PublicHome({ onAuth }) {
  return (
    <main className="public-shell">
      <header className="public-nav container">
        <Logo />
        <nav><a href="#how">How it works</a><a href="#impact">Our impact</a><a href="#mission">Our mission</a></nav>
        <button className="button button-outline" onClick={() => onAuth("login")}>Sign in <ArrowRight size={16} /></button>
      </header>
      <section className="hero container">
        <div className="hero-copy">
          <div className="eyebrow"><span className="pulse-dot" /> GOOD FOOD. BETTER TOMORROWS.</div>
          <h1>Every meal<br />deserves <em>a place.</em></h1>
          <p>We bring surplus food and the people who need it together — safely, thoughtfully, and right on time.</p>
          <div className="hero-actions"><button className="button button-primary" onClick={() => onAuth("register")}>Join the movement <ArrowRight size={17} /></button><a className="text-link" href="#how">See how it works <span>↓</span></a></div>
          <div className="hero-trust"><div className="avatar-stack"><i>R</i><i>A</i><i>S</i><i>+</i></div><span>Built for communities, by communities</span></div>
        </div>
        <div className="hero-art" aria-label="Illustration of a community food donation">
          <div className="sun-disc" /><div className="art-leaf leaf-one"><Leaf /></div><div className="art-leaf leaf-two"><Leaf /></div>
          <div className="art-card"><div className="meal-illustration"><div className="meal-bowl"><span /><i /><b /></div><div className="meal-leaf">✳</div></div><div className="rescue-note"><span className="note-icon"><Check size={14} /></span><div><b>Food rescued</b><small>Making a difference, together</small></div></div>
          <div className="floating-stat"><span className="stat-icon"><HandHeart size={17} /></span><span><b>One good meal</b><small>can change a day</small></span></div></div>
          <span className="art-caption">A little care goes a long way.</span>
        </div>
      </section>
      <section className="value-strip container"><div><span>01</span><b>Share surplus</b><small>Make good food count</small></div><ArrowRight /><div><span>02</span><b>Find your match</b><small>Connect with verified NGOs</small></div><ArrowRight /><div><span>03</span><b>Deliver with care</b><small>Track every step, together</small></div></section>
      <section className="mission-section container" id="mission"><div className="section-kicker">A BETTER WAY FORWARD</div><h2>Rescue food.<br /><em>Restore hope.</em></h2><p>Food should nourish people, not fill landfills. FoodBridge gives every plate with a little extra a direct path to a neighbor who needs it.</p><div className="mission-points"><span><CheckCircle2 size={17} /> Thoughtful, local matching</span><span><CheckCircle2 size={17} /> Safety at every handoff</span><span><CheckCircle2 size={17} /> Impact you can see</span></div></section>
      <section className="how-section" id="how"><div className="container"><div className="section-kicker">SIMPLE BY DESIGN</div><h2>Good food, <em>good hands.</em></h2><p className="section-intro">A clearer path from your kitchen to your community.</p><div className="how-cards"><article><div className="step-number">01</div><UtensilsCrossed /><h3>List your surplus</h3><p>Share what you have, how it was stored, and when it needs collecting.</p></article><article><div className="step-number">02</div><Sparkles /><h3>Find a good match</h3><p>Verified local organizations are matched to food they can put to use.</p></article><article><div className="step-number">03</div><Bike /><h3>Deliver with care</h3><p>A volunteer coordinates pickup. The receiving organization confirms delivery.</p></article></div></div></section>
      <section className="impact-banner container" id="impact"><div className="impact-icon"><Leaf size={27} /></div><div><div className="section-kicker">REAL FOOD. REAL COMMUNITY.</div><h2>Every rescued meal<br />is a little more <em>hope.</em></h2></div><p>Our impact dashboard only counts food from deliveries confirmed by the receiving organization. No guesswork. Just good done.</p><button className="button button-light" onClick={() => onAuth("register")}>Be part of it <ArrowRight size={16} /></button></section>
      <footer className="public-footer container"><Logo small /><span>Rescue Food. Restore Hope.</span><span>Made for people, with care. © FoodBridge</span></footer>
    </main>
  );
}

function AuthModal({ mode, close, onSuccess }) {
  const [formMode, setFormMode] = useState(mode);
  const [role, setRole] = useState("donor");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError("");
    const data = new FormData(event.currentTarget);
    const body = Object.fromEntries(data.entries());
    try {
      const { data: result } = await api.post(formMode === "login" ? "/auth/login" : "/auth/register", {
        ...body,
        ...(formMode === "register" ? { role } : {}),
      });
      localStorage.setItem("foodbridge-token", result.access_token);
      onSuccess(result.user);
    } catch (requestError) { setError(errorMessage(requestError)); }
    finally { setBusy(false); }
  }
  return <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && close()}><section className="auth-modal">
    <button className="icon-button modal-close" onClick={close} aria-label="Close"><X size={19} /></button>
    <Logo /><div className="section-kicker">{formMode === "login" ? "WELCOME BACK" : "LET'S DO SOME GOOD"}</div><h2>{formMode === "login" ? "Good to see you." : "Find your place."}</h2><p>{formMode === "login" ? "Sign in to pick up where you left off." : "Join a community making every meal matter."}</p>
    {formMode === "register" && <div className="role-picker">{[["donor", "I have food"], ["ngo", "We receive food"], ["volunteer", "I can help"]].map(([value, label]) => <button key={value} className={role === value ? "selected" : ""} type="button" onClick={() => setRole(value)}>{label}</button>)}</div>}
    <form onSubmit={submit} className="form-stack">
      {formMode === "register" && <Field label="Your name"><input name="name" required minLength="2" placeholder="How should we call you?" /></Field>}
      {formMode === "register" && role === "ngo" && <Field label="Organization name"><input name="organization_name" required placeholder="Your registered organization" /></Field>}
      {formMode === "register" && role === "volunteer" && <Field label="Phone number"><input name="phone" type="tel" autoComplete="tel" placeholder="You can add this in your profile" /></Field>}
      <Field label="Email address"><input name="email" type="email" required placeholder="you@example.org" /></Field>
      <Field label="Password"><input name="password" type="password" required minLength={formMode === "register" ? 10 : 1} placeholder={formMode === "register" ? "At least 10 characters" : "Your password"} /></Field>
      {error && <div className="error-box">{error}</div>}
      {formMode === "register" && <div className="info-box"><ShieldCheck size={16} /> NGO accounts need administrator verification before they can accept donations.</div>}
      <button className="button button-primary button-wide" disabled={busy}>{busy ? "One moment…" : formMode === "login" ? "Sign in" : "Create account"} <ArrowRight size={16} /></button>
    </form>
    <div className="auth-switch">{formMode === "login" ? "New to FoodBridge?" : "Already have an account?"} <button onClick={() => { setError(""); setFormMode(formMode === "login" ? "register" : "login"); }}> {formMode === "login" ? "Create an account" : "Sign in"}</button></div>
  </section></div>;
}

function StatCard({ icon: Icon, label, value, note, tone = "green" }) {
  return <article className={`stat-card stat-${tone}`}><div className="stat-top"><span className="stat-glyph"><Icon size={18} /></span><span className="stat-trend"><Activity size={13} /> Live</span></div><div className="stat-value">{value}</div><div className="stat-label">{label}</div><div className="stat-note">{note}</div></article>;
}

function StatusPill({ status }) {
  const label = (status || "").replaceAll("_", " ");
  return <span className={`status-pill status-${status}`}>{label}</span>;
}

function DonationCard({ donation, actions, onMatches, matches }) {
  return <article className="donation-card">
    <div className="donation-card-head"><span className="category-chip"><UtensilsCrossed size={13} /> {donation.category}</span><StatusPill status={donation.status} /></div>
    <h3>{donation.title}</h3><p className="donation-by">{donation.donor_name}{donation.ngo_name ? ` → ${donation.ngo_name}` : ""}</p>
    <div className="donation-facts"><span><HandHeart size={15} /> {donation.quantity_servings} servings</span><span><Clock3 size={15} /> Collect by {new Date(donation.pickup_deadline).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</span><span><MapPin size={15} /> {donation.pickup_address}</span></div>
    {donation.safety_note && <div className="warning-note">{donation.safety_note}</div>}
    {actions}
    {matches && <div className="match-list">{matches.map((match) => <div className="match-row" key={match.ngo_id}><div className="match-score">{Math.round(match.score)}<small>%</small></div><div><b>{match.organization_name}</b><small>{match.distance_km} km · Capacity {match.receiving_capacity} servings</small><small>{match.explanation}</small></div></div>)}</div>}
    {onMatches && <button className="button button-subtle button-small" onClick={() => onMatches(donation.id)}><Sparkles size={15} /> Find smart matches</button>}
  </article>;
}

function DonationForm({ onCreated }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError("");
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    data.quantity_servings = Number(data.quantity_servings);
    data.prepared_at = new Date(data.prepared_at).toISOString();
    data.pickup_deadline = new Date(data.pickup_deadline).toISOString();
    data.latitude = Number(data.latitude); data.longitude = Number(data.longitude);
    if (data.storage_temperature_c === "") delete data.storage_temperature_c;
    else data.storage_temperature_c = Number(data.storage_temperature_c);
    if (!data.photo_url) delete data.photo_url;
    try { await api.post("/donations", data); form.reset(); onCreated(); }
    catch (requestError) { setError(errorMessage(requestError)); }
    finally { setBusy(false); }
  }
  return <form className="panel form-panel" onSubmit={submit}><div className="panel-heading"><div><div className="section-kicker">A LITTLE EXTRA?</div><h2>Share a donation</h2><p>Tell us what you have and when it needs to be picked up.</p></div><span className="heading-icon"><Plus /></span></div>
    <div className="form-grid">
      <Field label="What are you sharing?"><input name="title" required minLength="3" placeholder="e.g. Freshly prepared lunch boxes" /></Field>
      <Field label="Food category"><select name="category">{categories.map((category) => <option key={category}>{category}</option>)}</select></Field>
      <Field label="Estimated servings"><input name="quantity_servings" type="number" min="1" defaultValue="20" required /></Field>
      <Field label="Prepared at"><input name="prepared_at" type="datetime-local" required /></Field>
      <Field label="Pickup deadline"><input name="pickup_deadline" type="datetime-local" required /></Field>
      <Field label="Storage method"><input name="storage_method" required placeholder="e.g. Refrigerated" /></Field>
      <Field label="Storage temperature °C (optional)"><input name="storage_temperature_c" type="number" step="any" min="-80" max="100" placeholder="e.g. 4" /></Field>
      <Field label="Packaging condition"><input name="packaging_condition" defaultValue="Sealed, food-safe containers" required /></Field>
      <Field label="Allergens"><input name="allergens" defaultValue="Not specified" /></Field>
      <Field label="Pickup address" className="field-full"><input name="pickup_address" required minLength="5" placeholder="Street address and locality" /></Field>
      <Field label="Pickup latitude"><input name="latitude" type="number" step="any" min="-90" max="90" required placeholder="e.g. 12.9716" /></Field>
      <Field label="Pickup longitude"><input name="longitude" type="number" step="any" min="-180" max="180" required placeholder="e.g. 77.5946" /></Field>
      <Field label="Food photo URL (optional)" className="field-full"><input name="photo_url" type="url" placeholder="https://…" /></Field>
    </div>
    <div className="safety-note"><ShieldCheck size={17} /><span><b>Food safety comes first.</b> Only list food you can responsibly confirm was handled and stored appropriately. A photo cannot determine whether food is safe.</span></div>
    {error && <div className="error-box">{error}</div>}
    <button className="button button-primary" disabled={busy}>{busy ? "Sharing…" : "Publish donation"} <ArrowRight size={16} /></button>
  </form>;
}

function ProfileForm({ user, refresh }) {
  const [profile, setProfile] = useState(user.ngo_profile ? {
    ...emptyProfile,
    ...user.ngo_profile,
    accepted_categories: user.ngo_profile.accepted_categories.includes("all") ? categories : user.ngo_profile.accepted_categories,
  } : emptyProfile);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function save(event) {
    event.preventDefault(); setMessage(""); setError("");
    try {
      const response = await api.put("/ngo/profile", { ...profile, receiving_capacity: Number(profile.receiving_capacity), latitude: Number(profile.latitude), longitude: Number(profile.longitude) });
      localStorage.setItem("foodbridge-user", JSON.stringify(response.data));
      setMessage("Organization profile saved. Your NGO remains subject to verification.");
      refresh();
    } catch (requestError) { setError(errorMessage(requestError)); }
  }
  function update(key, value) { setProfile((current) => ({ ...current, [key]: value })); }
  return <form className="panel form-panel profile-form" onSubmit={save}><div className="section-kicker">YOUR ORGANIZATION</div><h2>Help us find your best matches.</h2><p className="muted">Set your service area and capacity. Matching uses these details and only recommends verified NGOs.</p>
    <div className="form-grid"><Field label="Service area"><input value={profile.service_area} onChange={(e) => update("service_area", e.target.value)} required minLength="2" placeholder="e.g. Indiranagar, Bengaluru" /></Field><Field label="Receiving capacity (servings)"><input type="number" value={profile.receiving_capacity} onChange={(e) => update("receiving_capacity", e.target.value)} min="1" required /></Field><Field label="Latitude"><input type="number" step="any" value={profile.latitude ?? ""} onChange={(e) => update("latitude", e.target.value)} required /></Field><Field label="Longitude"><input type="number" step="any" value={profile.longitude ?? ""} onChange={(e) => update("longitude", e.target.value)} required /></Field><div className="field field-full"><span>Food categories you accept</span><div className="category-select">{categories.map((category) => <label key={category}><input type="checkbox" checked={profile.accepted_categories.includes(category)} onChange={(e) => update("accepted_categories", e.target.checked ? [...profile.accepted_categories, category] : profile.accepted_categories.filter((item) => item !== category))} /> {category}</label>)}</div></div></div>
    {message && <div className="success-box"><CheckCircle2 size={16} />{message}</div>}{error && <div className="error-box">{error}</div>}<button className="button button-primary">Save organization profile <ArrowRight size={16} /></button>
  </form>;
}

function DeliveryCard({ delivery, user, refresh }) {
  const [candidates, setCandidates] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function act(request) { setBusy(true); setError(""); try { await request(); refresh(); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } }
  async function getCandidates() {
    setError("");
    try { const { data } = await api.get(`/volunteers/recommendations/${delivery.id}`); setCandidates(data); }
    catch (e) { setError(errorMessage(e)); }
  }
  const volunteerActions = user.role === "volunteer" && delivery.status === "volunteer_assigned" ? <><button className="button button-primary button-small" disabled={busy} onClick={() => act(() => api.post(`/deliveries/${delivery.id}/accept-task`))}>Accept task <Check size={14} /></button><button className="button button-outline button-small" disabled={busy} onClick={() => act(() => api.post(`/deliveries/${delivery.id}/status`, { status: "failed_pickup", note: "Volunteer declined the assignment." }))}>Decline</button></> : null;
  const destination = delivery.destination_address || delivery.ngo_name;
  const mapsUrl = (address) => `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(address)}`;
  const distanceKm = delivery.donation?.latitude != null && delivery.destination_latitude != null
    ? Math.round((6371 * 2 * Math.asin(Math.sqrt(
      Math.sin(((delivery.destination_latitude - delivery.donation.latitude) * Math.PI) / 360) ** 2 +
      Math.cos((delivery.donation.latitude * Math.PI) / 180) * Math.cos((delivery.destination_latitude * Math.PI) / 180) *
      Math.sin(((delivery.destination_longitude - delivery.donation.longitude) * Math.PI) / 360) ** 2,
    ))) * 10) / 10
    : null;
  return <article className="delivery-card">
    <div className="delivery-header"><div><div className="section-kicker">DELIVERY #{delivery.id}</div><h3>{delivery.donation?.title}</h3></div><StatusPill status={delivery.status} /></div>
    <div className="delivery-route"><div><span className="route-dot route-origin" /><small>PICKUP</small><b>{delivery.donation?.pickup_address}</b><a className="text-link" href={mapsUrl(delivery.donation?.pickup_address || "")} target="_blank" rel="noreferrer">Navigate to pickup <ArrowRight size={13} /></a></div><span className="route-line" /><div><span className="route-dot route-dest" /><small>DROP-OFF</small><b>{destination}</b><a className="text-link" href={mapsUrl(destination)} target="_blank" rel="noreferrer">Navigate to drop-off <ArrowRight size={13} /></a></div></div>
    {distanceKm !== null && <div className="volunteer-note"><MapPin size={15} /> Approx. {distanceKm} km straight-line · ~{Math.max(1, Math.round(distanceKm * 3))} min estimated</div>}
    {delivery.volunteer_name && <div className="volunteer-note"><Bike size={15} /> Volunteer: {delivery.volunteer_name}</div>}
    <div className="timeline">{delivery.history?.map((event, index) => <span key={`${event.status}-${index}`} title={event.note}><i />{event.status.replaceAll("_", " ")}</span>)}</div>
    <div className="card-actions">
      {["ngo", "admin"].includes(user.role) && ["accepted", "volunteer_assigned", "failed_pickup"].includes(delivery.status) && <button className="button button-subtle button-small" onClick={getCandidates}><Search size={14} /> Recommend volunteers</button>}
      {user.role === "ngo" && delivery.status === "delivered" && <button className="button button-primary button-small" disabled={busy} onClick={() => act(() => api.post(`/deliveries/${delivery.id}/receipt`))}>Confirm receipt <CheckCircle2 size={14} /></button>}
      {user.role === "volunteer" && delivery.status === "volunteer_accepted" && <button className="button button-primary button-small" disabled={busy} onClick={() => act(() => api.post(`/deliveries/${delivery.id}/status`, { status: "pickup_confirmed" }))}>Confirm pickup</button>}
      {user.role === "volunteer" && ["pickup_confirmed", "in_transit"].includes(delivery.status) && <button className="button button-primary button-small" disabled={busy} onClick={() => {
        if (delivery.status === "pickup_confirmed") return act(() => api.post(`/deliveries/${delivery.id}/status`, { status: "in_transit" }));
        const proofUrl = window.prompt("Enter the HTTPS link to delivery proof (photo or receipt).");
        if (!proofUrl) return;
        try { if (new URL(proofUrl).protocol !== "https:") throw new Error("Use a secure HTTPS link."); }
        catch (e) { setError(e.message || "Enter a valid proof URL."); return; }
        act(() => api.post(`/deliveries/${delivery.id}/status`, { status: "delivered", proof_url: proofUrl, note: "Delivery proof link recorded." }));
      }}>{delivery.status === "pickup_confirmed" ? "Start transit" : "Add proof & confirm delivery"}</button>}
      {volunteerActions}
      {user.role === "volunteer" && ["volunteer_assigned", "volunteer_accepted", "pickup_confirmed"].includes(delivery.status) && <button className="button button-subtle button-small" disabled={busy} onClick={() => act(() => api.post(`/deliveries/${delivery.id}/status`, { status: "failed_pickup", note: "Unable to complete pickup." }))}>Unable to pick up</button>}
      {user.role !== "admin" && !["completed", "safety_incident", "failed_pickup"].includes(delivery.status) && <button className="link-danger" onClick={() => { const description = window.prompt("Describe the food safety concern (at least 10 characters)."); if (description && description.length >= 10) act(() => api.post(`/donations/${delivery.donation.id}/safety-reports`, { description })); }}>Report a safety concern</button>}
    </div>
    {candidates.length > 0 && <div className="candidate-list"><b>Available nearby volunteers</b>{candidates.map((candidate) => <div key={candidate.volunteer_id}><span>{candidate.name}<small>{candidate.distance_km} km away</small></span><button className="button button-small button-outline" disabled={busy} onClick={() => act(() => api.post(`/deliveries/${delivery.id}/assign`, { volunteer_id: candidate.volunteer_id }))}>Assign <ArrowRight size={13} /></button></div>)}</div>}
    {error && <div className="error-box">{error}</div>}
  </article>;
}

function Dashboard({ user, setUser, logout }) {
  const [activeNav, setActiveNav] = useState("Overview");
  const [mobileMenu, setMobileMenu] = useState(false);
  const [donations, setDonations] = useState([]);
  const [deliveries, setDeliveries] = useState([]);
  const [impact, setImpact] = useState(null);
  const [matches, setMatches] = useState({});
  const [applications, setApplications] = useState([]);
  const [volunteers, setVolunteers] = useState([]);
  const [people, setPeople] = useState([]);
  const [safetyReports, setSafetyReports] = useState([]);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [chartData, setChartData] = useState([]);
  const previousDeliveryStatuses = useRef(null);
  const nav = navByRole[user.role] || navByRole.donor;
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [donationResponse, deliveryResponse, impactResponse, trendsResponse] = await Promise.all([
        api.get("/donations"), api.get("/deliveries"), api.get("/impact"), api.get("/impact/trends"),
      ]);
      setDonations(donationResponse.data); setDeliveries(deliveryResponse.data); setImpact(impactResponse.data);
      const currentStatuses = Object.fromEntries(deliveryResponse.data.map((delivery) => [delivery.id, delivery.status]));
      if (previousDeliveryStatuses.current) {
        const changed = deliveryResponse.data.find((delivery) => previousDeliveryStatuses.current[delivery.id] && previousDeliveryStatuses.current[delivery.id] !== delivery.status);
        if (changed) setNotice(`Delivery #${changed.id} status updated: ${changed.status.replaceAll("_", " ")}.`);
      }
      previousDeliveryStatuses.current = currentStatuses;
      setChartData(trendsResponse.data);
      if (user.role === "admin") {
        const [ngos, users, reports, volunteerResponse] = await Promise.all([api.get("/admin/ngos"), api.get("/admin/users"), api.get("/admin/safety-reports"), api.get("/admin/volunteers")]);
        setApplications(ngos.data); setPeople(users.data); setSafetyReports(reports.data); setVolunteers(volunteerResponse.data);
      }
    } catch (requestError) { setNotice(errorMessage(requestError)); }
    finally { setLoading(false); }
  }, [user.role]);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    const timer = window.setInterval(refresh, 15000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function loadMatches(id) {
    setNotice("");
    try { const { data } = await api.get(`/donations/${id}/matches`); setMatches((current) => ({ ...current, [id]: data })); }
    catch (requestError) { setNotice(errorMessage(requestError)); }
  }
  async function action(request, success) {
    setNotice("");
    try { await request(); setNotice(success); await refresh(); }
    catch (requestError) { setNotice(errorMessage(requestError)); }
  }
  async function reviewNGO(id, decision) {
    await action(() => api.post(`/admin/ngos/${id}/review`, null, { params: { decision } }), `Application ${decision}.`);
  }
  async function reviewVolunteer(id, decision) {
    await action(() => api.post(`/admin/volunteers/${id}/review`, null, { params: { decision } }), `Volunteer application ${decision}.`);
  }
  const title = activeNav === "Overview" ? "A little good, every day." : activeNav;
  const assignedDonations = donations.filter((item) => item.status !== "awaiting_match");
  const isPendingNGO = user.role === "ngo" && user.ngo_profile?.verification_status !== "approved";
  const isPendingVolunteer = user.role === "volunteer" && user.volunteer_profile?.verification_status !== "approved";

  return <div className="app-shell">
    <aside className={`sidebar ${mobileMenu ? "sidebar-open" : ""}`}>
      <div className="sidebar-brand"><Logo /><button className="icon-button sidebar-close" onClick={() => setMobileMenu(false)}><X size={18} /></button></div>
      <div className="workspace-switch"><span className="workspace-monogram">{user.name?.slice(0, 1).toUpperCase()}</span><span><b>{user.name}</b><small>{roleTitles[user.role]}</small></span><ChevronDown size={15} /></div>
      <div className="side-label">WORKSPACE</div>
      <nav className="side-nav">{nav.map(([label, Icon]) => <button className={activeNav === label ? "active" : ""} key={label} onClick={() => { setActiveNav(label); setMobileMenu(false); }}><Icon size={18} /><span>{label}</span>{label === "NGO verification" && applications.some((item) => item.verification_status === "pending") && <i className="nav-indicator" />}</button>)}</nav>
      <div className="sidebar-bottom"><div className="safety-reminder"><ShieldCheck size={18} /><b>Safety is shared.</b><p>Handle, transport and receive every donation with care.</p></div><button className="logout-button" onClick={logout}><LogOut size={17} /> Sign out</button><small className="sidebar-foot">FoodBridge · Community edition</small></div>
    </aside>
    <main className="dashboard-main">
      <header className="topbar"><button className="icon-button menu-button" onClick={() => setMobileMenu(true)}><Menu size={20} /></button><div className="breadcrumb">Workspace <span>/</span> <b>{activeNav}</b></div><div className="topbar-right"><span className="live-indicator"><i /> Updates every 15 sec</span><button className="icon-button notification-button" aria-label="Refresh notifications and delivery updates" title="Refresh updates" onClick={refresh}><Bell size={18} /></button><button className="user-avatar" onClick={() => setActiveNav(user.role === "ngo" ? "Organization profile" : "Overview")}>{user.name?.slice(0, 1).toUpperCase()}</button></div></header>
      <div className="content">
        <div className="page-heading"><div><div className="section-kicker">{new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }).toUpperCase()}</div><h1>{title}</h1><p>{user.role === "donor" ? "Your surplus can make somebody's day." : user.role === "ngo" ? "Good food is finding its way to your community." : user.role === "volunteer" ? "Small acts of care make a big difference." : "A clearer view of good happening across the network."}</p></div><div className="heading-actions"><span className="verification-tag"><ShieldCheck size={15} /> {user.role === "ngo" ? user.ngo_profile?.verification_status === "approved" ? "Verified organization" : "Verification pending" : "Verified & secure"}</span></div></div>
        {notice && <div className={notice.includes("wrong") || notice.includes("required") ? "error-box notice-box" : "success-box notice-box"}><span>{notice}</span><button onClick={() => setNotice("")}><X size={15} /></button></div>}
        {isPendingNGO && <div className="pending-banner"><ShieldCheck size={20} /><div><b>Your organization is awaiting verification</b><p>Complete your profile while an administrator reviews your application. Only verified NGOs can accept food donations.</p></div><button className="button button-outline button-small" onClick={() => setActiveNav("Organization profile")}>Complete profile</button></div>}
        {isPendingVolunteer && <div className="pending-banner"><ShieldCheck size={20} /><div><b>Your volunteer profile is awaiting approval</b><p>Complete your contact and service-area details. You can receive delivery assignments after an administrator approves your registration.</p></div><button className="button button-outline button-small" onClick={() => setActiveNav("My profile")}>Complete profile</button></div>}
        {activeNav === "Overview" && <Overview user={user} impact={impact} donations={donations} deliveries={deliveries} chartData={chartData} setActiveNav={setActiveNav} loading={loading} />}
        {activeNav === "My donations" && <section className="workspace-grid"><div className="workspace-primary"><div className="section-header"><div><div className="section-kicker">YOUR CONTRIBUTION</div><h2>Donation history</h2></div><span className="count-badge">{donations.length} total</span></div><div className="donation-list">{donations.length ? donations.map((donation) => <DonationCard key={donation.id} donation={donation} onMatches={loadMatches} matches={matches[donation.id]} />) : <EmptyState icon={UtensilsCrossed} title="Your next donation starts here" body="Post surplus food and we’ll help connect it with verified local NGOs." />}</div></div><div className="workspace-secondary"><DonationForm onCreated={refresh} /></div></section>}
        {activeNav === "Smart matches" && <section className="panel"><div className="section-kicker">THOUGHTFUL CONNECTIONS</div><h2>Smart matches</h2><p className="muted">Recommendations use verified NGO profiles, category compatibility, capacity, distance, pickup urgency and current volunteer availability.</p><div className="donation-list">{donations.filter((item) => item.status === "awaiting_match").map((donation) => <DonationCard key={donation.id} donation={donation} onMatches={loadMatches} matches={matches[donation.id]} />)}{!donations.some((item) => item.status === "awaiting_match") && <EmptyState icon={Sparkles} title="No open donations to match" body="When you post an eligible donation, recommendations will appear here." />}</div></section>}
        {activeNav === "Nearby food" && <section className="panel"><div className="section-kicker">VERIFIED DONATIONS NEAR YOU</div><h2>Good food, close by.</h2><p className="muted">Only eligible, unexpired listings are shown. Review handling details before you accept a donation.</p><div className="donation-list">{donations.filter((item) => item.status === "awaiting_match").map((donation) => <DonationCard key={donation.id} donation={donation} actions={<button className="button button-primary button-small" disabled={isPendingNGO} onClick={() => action(() => api.post(`/donations/${donation.id}/accept`), "Donation accepted. Next, assign a volunteer.")}>Accept donation <ArrowRight size={14} /></button>} />)}{!donations.some((item) => item.status === "awaiting_match") && <EmptyState icon={Compass} title="No nearby listings right now" body="Check again soon. New community donations appear here." />}</div></section>}
        {activeNav === "Deliveries" && <section className="panel"><div className="section-header"><div><div className="section-kicker">HANDOFF, STEP BY STEP</div><h2>{user.role === "ngo" ? "Incoming deliveries" : "Delivery tracking"}</h2></div><span className="count-badge">{deliveries.length} active & past</span></div><div className="delivery-list">{deliveries.map((delivery) => <DeliveryCard key={delivery.id} delivery={delivery} user={user} refresh={refresh} />)}{!deliveries.length && <EmptyState icon={Bike} title="No deliveries yet" body="Your accepted donations and assigned volunteer tasks will be tracked here." />}</div></section>}
        {activeNav === "My tasks" && <section className="panel"><div className="section-kicker">YOUR COMMUNITY, ON THE MOVE</div><h2>Volunteer tasks</h2><p className="muted">Tasks assigned to you appear below. Record the pickup, transit and handoff status as each step happens.</p><div className="delivery-list">{deliveries.map((delivery) => <DeliveryCard key={delivery.id} delivery={delivery} user={user} refresh={refresh} />)}{!deliveries.length && <EmptyState icon={Bike} title="Nothing assigned just yet" body="Keep your availability profile up to date so NGOs can find you." />}</div></section>}
        {activeNav === "Organization profile" && <ProfileForm user={user} refresh={async () => { const { data } = await api.get("/auth/me"); setUser(data); localStorage.setItem("foodbridge-user", JSON.stringify(data)); }} />}
        {activeNav === "My profile" && <VolunteerProfile user={user} />}
        {activeNav === "NGO verification" && <AdminNGOs applications={applications} review={reviewNGO} />}
        {activeNav === "Volunteer management" && <AdminVolunteers volunteers={volunteers} review={reviewVolunteer} />}
        {activeNav === "People" && <AdminPeople people={people} action={action} />}
        {activeNav === "Food safety" && <AdminSafety reports={safetyReports} />}
      </div>
    </main>
  </div>;
}

function Overview({ user, impact, donations, deliveries, chartData, setActiveNav, loading }) {
  const completed = deliveries.filter((delivery) => delivery.status === "completed").length;
  const openCount = donations.filter((donation) => donation.status === "awaiting_match").length;
  const stats = user.role === "admin" ? [
    [HandHeart, "Verified NGOs", impact?.verified_ngos ?? "—", "Approved organizations"],
    [UtensilsCrossed, "Food rescued", `${(impact?.rescued_servings ?? 0).toLocaleString()}`, "Confirmed servings"],
    [Bike, "Successful deliveries", impact?.successful_deliveries ?? 0, "Receipt confirmed"],
    [ShieldCheck, "Safety reports", "Review", "Investigate open reports", "orange"],
  ] : user.role === "volunteer" ? [
    [Bike, "Assigned tasks", deliveries.length, "Across your service area"],
    [CheckCircle2, "Completed", completed, "Your confirmed handoffs"],
    [HandHeart, "Community meals", "—", "Counted after NGO confirmation"],
    [Clock3, "Ready to help", "Set availability", "Update your volunteer profile", "orange"],
  ] : user.role === "ngo" ? [
    [Compass, "Nearby donations", openCount, "Eligible listings"],
    [Bike, "Incoming deliveries", deliveries.filter((delivery) => delivery.status !== "completed").length, "Accepted & in progress"],
    [CheckCircle2, "Received", completed, "Receipt-confirmed deliveries"],
    [HandHeart, "Servings received", impact?.rescued_servings ?? 0, "Network-wide confirmed total", "orange"],
  ] : [
    [UtensilsCrossed, "Your donations", donations.length, "Shared with your community"],
    [Sparkles, "Open to match", openCount, "Eligible & awaiting an NGO"],
    [Bike, "Active deliveries", deliveries.filter((delivery) => delivery.status !== "completed").length, "Tracked handoffs"],
    [CheckCircle2, "Meals rescued", impact?.rescued_servings ?? 0, "Confirmed network total", "orange"],
  ];
  return <><div className="stats-grid">{stats.map(([Icon, label, value, note, tone]) => <StatCard key={label} icon={Icon} label={label} value={loading ? "…" : value} note={note} tone={tone} />)}</div>
    <div className="overview-grid"><section className="panel chart-panel"><div className="section-header"><div><div className="section-kicker">A WEEK OF GOOD</div><h2>Community impact</h2></div><span className="estimate-label"><span /> Confirmed deliveries only</span></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}><defs><linearGradient id="mealGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#37835f" stopOpacity={0.24} /><stop offset="90%" stopColor="#37835f" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#e9eee8" vertical={false} /><XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: "#829087", fontSize: 12 }} dy={10} /><YAxis axisLine={false} tickLine={false} tick={{ fill: "#829087", fontSize: 11 }} /><Tooltip /><Area type="monotone" dataKey="meals" stroke="#37835f" strokeWidth={2.5} fill="url(#mealGradient)" /></AreaChart></ResponsiveContainer></div><p className="chart-footnote">Trend data appears as confirmed deliveries are recorded. Meal totals are estimates based on servings reported by donors.</p></section>
      <section className="panel activity-panel"><div className="section-header"><div><div className="section-kicker">RECENT ACTIVITY</div><h2>Good things in motion</h2></div><span className="live-dot-label"><i /> Live</span></div><div className="activity-feed">{deliveries.slice(0, 4).map((delivery) => <div className="activity-item" key={delivery.id}><span className="activity-icon"><PackageCheck size={16} /></span><div><b>{delivery.donation?.title || "Food delivery"}</b><p>{delivery.status.replaceAll("_", " ")} · {delivery.ngo_name}</p></div><StatusPill status={delivery.status} /></div>)}{!deliveries.length && <div className="activity-empty"><span className="empty-illustration"><HeartHandshake size={25} /></span><b>Your community story starts here</b><p>Once a donation is accepted, its journey will show up here.</p>{(user.role === "donor" || user.role === "ngo") && <button className="text-link" onClick={() => setActiveNav(user.role === "donor" ? "My donations" : "Nearby food")}>{user.role === "donor" ? "Share a donation" : "Explore nearby food"} <ArrowRight size={14} /></button>}</div>}</div></section></div>
    {user.role === "donor" && <div className="quick-action"><div className="quick-icon"><Plus /></div><div><b>Have a little extra to share?</b><p>Post a donation and let a nearby community put it to good use.</p></div><button className="button button-primary" onClick={() => setActiveNav("My donations")}>Share surplus <ArrowRight size={15} /></button></div>}
    {user.role === "ngo" && user.ngo_profile?.verification_status === "approved" && <div className="quick-action"><div className="quick-icon"><Compass /></div><div><b>Food might be closer than you think.</b><p>Explore eligible donations and accept what your community can use.</p></div><button className="button button-primary" onClick={() => setActiveNav("Nearby food")}>Browse nearby food <ArrowRight size={15} /></button></div>}
  </>;
}

function VolunteerProfile({ user }) {
  const [message, setMessage] = useState(""); const [error, setError] = useState("");
  const [profile, setProfile] = useState({
    phone: user.volunteer_profile?.phone ?? "",
    available: user.volunteer_profile?.available ?? true,
    service_area: user.volunteer_profile?.service_area ?? "",
    latitude: user.volunteer_profile?.latitude ?? "",
    longitude: user.volunteer_profile?.longitude ?? "",
  });
  async function save(event) {
    event.preventDefault(); setMessage(""); setError("");
    try { await api.put("/volunteer/profile", { ...profile, latitude: Number(profile.latitude), longitude: Number(profile.longitude) }); setMessage("Your volunteer profile and availability have been saved."); }
    catch (requestError) { setError(errorMessage(requestError)); }
  }
  return <form className="panel form-panel profile-form" onSubmit={save}><div className="section-kicker">YOUR VOLUNTEER PROFILE</div><h2>Show up where you’re needed.</h2><p className="muted">Set an approximate service location so NGOs can recommend feasible pickup tasks.</p><div className="form-grid"><Field label="Phone number"><input type="tel" autoComplete="tel" value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} required minLength="7" maxLength="30" /></Field><Field label="Service area"><input value={profile.service_area} onChange={(e) => setProfile({ ...profile, service_area: e.target.value })} required placeholder="e.g. Koramangala, Bengaluru" /></Field><Field label="Latitude"><input type="number" step="any" value={profile.latitude} onChange={(e) => setProfile({ ...profile, latitude: e.target.value })} required /></Field><Field label="Longitude"><input type="number" step="any" value={profile.longitude} onChange={(e) => setProfile({ ...profile, longitude: e.target.value })} required /></Field><label className="availability-toggle"><input type="checkbox" checked={profile.available} onChange={(e) => setProfile({ ...profile, available: e.target.checked })} /> I’m available to help with a delivery</label></div>{message && <div className="success-box">{message}</div>}{error && <div className="error-box">{error}</div>}<button className="button button-primary">Save volunteer profile <ArrowRight size={16} /></button></form>;
}

function EmptyState({ icon: Icon, title, body }) {
  return <div className="empty-state"><span className="empty-illustration"><Icon size={24} /></span><b>{title}</b><p>{body}</p></div>;
}

function AdminNGOs({ applications, review }) {
  return <section className="panel"><div className="section-kicker">BUILDING TRUST, TOGETHER</div><h2>NGO verification</h2><p className="muted">Only approved organizations can accept donations. Review identity documents through your secure administrative process before approval.</p><div className="admin-list">{applications.map((application) => <article key={application.user_id}><div className="admin-user-icon"><ShieldCheck size={18} /></div><div className="admin-user-details"><b>{application.name}</b><small>{application.email} · {application.service_area || "Service area not set"}</small></div><StatusPill status={application.verification_status} />{application.verification_status === "pending" && <div className="card-actions"><button className="button button-primary button-small" onClick={() => review(application.user_id, "approved")}>Approve</button><button className="button button-outline button-small" onClick={() => review(application.user_id, "rejected")}>Reject</button></div>}</article>)}{!applications.length && <EmptyState icon={ShieldCheck} title="No applications yet" body="New NGO applications will appear here for review." />}</div></section>;
}

function AdminVolunteers({ volunteers, review }) {
  return <section className="panel"><div className="section-kicker">SAFE, TRUSTED DELIVERIES</div><h2>Volunteer management</h2><p className="muted">Review volunteer registrations before they can be assigned delivery tasks.</p><div className="admin-list">{volunteers.map((volunteer) => <article key={volunteer.user_id}><div className="admin-user-icon"><Bike size={18} /></div><div className="admin-user-details"><b>{volunteer.name}</b><small>{volunteer.email} · {volunteer.phone || "Phone not provided"} · {volunteer.service_area || "Service area not set"}</small></div><StatusPill status={volunteer.verification_status} />{volunteer.verification_status === "pending" && <div className="card-actions"><button className="button button-primary button-small" disabled={(volunteer.phone || "").replace(/\D/g, "").length < 7} onClick={() => review(volunteer.user_id, "approved")}>Approve</button><button className="button button-outline button-small" onClick={() => review(volunteer.user_id, "rejected")}>Reject</button></div>}</article>)}{!volunteers.length && <EmptyState icon={Bike} title="No volunteer registrations yet" body="Volunteer applications will appear here for review." />}</div></section>;
}

function AdminPeople({ people, action }) {
  return <section className="panel"><div className="section-kicker">THE PEOPLE BEHIND THE GOOD</div><h2>People & accounts</h2><div className="admin-list">{people.map((person) => <article key={person.id}><div className="admin-user-icon"><HandHeart size={18} /></div><div className="admin-user-details"><b>{person.name}</b><small>{person.email} · {roleTitles[person.role]}</small></div><StatusPill status={person.is_active ? "active" : "suspended"} />{person.role !== "admin" && <button className="button button-outline button-small" onClick={() => action(() => api.post(`/admin/users/${person.id}/suspend`, null, { params: { suspended: person.is_active } }), person.is_active ? "Account suspended." : "Account reactivated.")}>{person.is_active ? "Suspend" : "Reactivate"}</button>}</article>)}</div></section>;
}

function AdminSafety({ reports }) {
  return <section className="panel"><div className="section-kicker">CARE COMES FIRST</div><h2>Food safety reports</h2><p className="muted">Every report places the donation on hold and is reviewed by the platform team.</p><div className="admin-list">{reports.map((report) => <article key={report.id}><div className="admin-user-icon warning-icon"><ShieldCheck size={18} /></div><div className="admin-user-details"><b>Donation #{report.donation_id}</b><small>{report.description}</small></div><StatusPill status={report.status} /></article>)}{!reports.length && <EmptyState icon={ShieldCheck} title="No safety reports" body="Reports submitted by a participant will be listed here." />}</div></section>;
}

export default function App() {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("foodbridge-user")); } catch { return null; }
  });
  const [authMode, setAuthMode] = useState("");
  useEffect(() => {
    if (!localStorage.getItem("foodbridge-token")) return;
    api.get("/auth/me").then(({ data }) => { setUser(data); localStorage.setItem("foodbridge-user", JSON.stringify(data)); })
      .catch(() => { localStorage.removeItem("foodbridge-token"); localStorage.removeItem("foodbridge-user"); setUser(null); });
  }, []);
  function onSuccess(newUser) { setUser(newUser); localStorage.setItem("foodbridge-user", JSON.stringify(newUser)); setAuthMode(""); }
  function logout() { localStorage.removeItem("foodbridge-token"); localStorage.removeItem("foodbridge-user"); setUser(null); }
  return user ? <Dashboard user={user} setUser={setUser} logout={logout} /> : <><PublicHome onAuth={setAuthMode} />{authMode && <AuthModal mode={authMode} close={() => setAuthMode("")} onSuccess={onSuccess} />}</>;
}
