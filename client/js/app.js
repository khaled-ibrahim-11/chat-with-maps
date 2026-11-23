const empty = { type: "FeatureCollection", features: [] };
const $ = selector => document.querySelector(selector);
const question = $("#question"), form = $("#chat-form"), messages = $("#messages");
const mapStatus = $("#map-status"), mapKey = $("#map-key"), areaKey = $("#area-key");
let map, mapReady = false, latest = { features: empty, search_area: null };
let sessions = [], currentId = null, activeRequest = null;
const storageKey = "chat-with-maps.conversations.v1";
try {
  const stored = JSON.parse(localStorage.getItem(storageKey) || "[]");
  if (Array.isArray(stored)) sessions = stored.filter(s => s && typeof s.id === "string" && typeof s.title === "string" && Array.isArray(s.messages)).slice(0, 20);
} catch { /* Chat remains available without browser storage. */ }
function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "#i-" + name); svg.append(use); return svg;
}
function save() {
  try { localStorage.setItem(storageKey, JSON.stringify(sessions.slice(0, 20))); }
  catch { $("#composer-caption").textContent = "Device storage is unavailable or full. This conversation is available for this visit."; }
  renderHistory();
}
function renderHistory() {
  $("#history-list").replaceChildren(); $("#history-empty").hidden = sessions.length > 0;
  for (const session of sessions) {
    const button = document.createElement("button");
    button.className = "history-item" + (session.id === currentId ? " active" : "");
    button.textContent = session.title; button.title = session.title;
    if (session.id === currentId) button.setAttribute("aria-current", "true");
    button.addEventListener("click", () => openSession(session)); $("#history-list").append(button);
  }
}
function scrollChat() { $("#chat-scroll").scrollTop = $("#chat-scroll").scrollHeight; }
function renderMessage(message) {
  $("#welcome").hidden = true; messages.hidden = false;
  const article = document.createElement("article");
  article.className = "message " + message.role + (message.error ? " error" : "");
  article.setAttribute("aria-label", message.role === "user" ? "You" : "Maps assistant");
  if (message.role === "assistant") {
    const heading = document.createElement("div"); heading.className = "assistant-heading";
    heading.append(icon("compass"), "Maps assistant"); article.append(heading);
  }
  const text = document.createElement("p"); text.className = "message-text"; text.textContent = message.text; article.append(text);
  const data = message.data;
  if (data?.features?.features?.length) {
    const details = document.createElement("details"); details.className = "result-details"; details.open = true;
    const summary = document.createElement("summary"); summary.textContent = data.features.features.length.toLocaleString() + " matching places";
    const scroll = document.createElement("div"); scroll.className = "table-scroll";
    const table = document.createElement("table"); table.setAttribute("aria-label", "Matching places");
    const head = table.createTHead().insertRow(), distance = Boolean(data.search_area);
    for (const title of ["Place", "Locality", ...(distance ? ["Distance"] : [])]) {
      const th = document.createElement("th"); th.scope = "col"; th.textContent = title; head.append(th);
    }
    const body = table.createTBody();
    for (const feature of data.features.features) {
      const props = feature.properties || {}, row = body.insertRow();
      row.insertCell().textContent = props.POI_Name_English || "Unnamed place";
      row.insertCell().textContent = props.Locality || "—";
      if (distance) row.insertCell().textContent = Number.isFinite(props.distance_m) ? Math.round(props.distance_m) + " m" : "—";
    }
    scroll.append(table); details.append(summary, scroll);
    const view = document.createElement("button"); view.className = "view-results";
    view.append(icon("map"), "View these places on the map");
    view.addEventListener("click", () => { setMapData(data); });
    article.append(details, view);
  }
  messages.append(article); return article;
}
function setMapData(data) {
  latest = data;
  updateMap();
}
function cancelRequest() { if (activeRequest) activeRequest.abort(); activeRequest = null; form.removeAttribute("aria-busy"); updateComposer(); }
function closeSidebar() { document.body.classList.remove("sidebar-open"); syncSidebar(); }
function openSession(session) {
  cancelRequest(); currentId = session?.id || null; messages.replaceChildren(); messages.hidden = true; $("#welcome").hidden = false;
  let data = { features: empty, search_area: null };
  for (const message of session?.messages || []) { renderMessage(message); if (message.data && !message.data.is_greeting) data = message.data; }
  setMapData(data);
  if (!session && mapReady) map.jumpTo({ center: [55.273, 25.205], zoom: 11 });
  question.value = ""; updateComposer(); renderHistory(); closeSidebar(); scrollChat(); question.focus();
}
function updateComposer() {
  question.style.height = "auto"; question.style.height = Math.min(140, Math.max(40, question.scrollHeight)) + "px";
  $("#send").disabled = !question.value.trim() || Boolean(activeRequest);
  document.querySelectorAll("[data-question]").forEach(button => { button.disabled = Boolean(activeRequest); });
}
function syncSidebar() {
  const visible = matchMedia("(max-width: 760px)").matches ? document.body.classList.contains("sidebar-open") : !document.body.classList.contains("sidebar-closed");
  $("#toggle-sidebar").setAttribute("aria-expanded", String(visible));
}
$("#toggle-sidebar").addEventListener("click", () => {
  document.body.classList.toggle(matchMedia("(max-width: 760px)").matches ? "sidebar-open" : "sidebar-closed"); syncSidebar();
});
$("#close-sidebar").addEventListener("click", () => { closeSidebar(); $("#toggle-sidebar").focus(); });
$(".backdrop").addEventListener("click", closeSidebar);
$("#new-chat").addEventListener("click", () => openSession(null));
$("#reset-map").addEventListener("click", () => { if (mapReady) map.jumpTo({ center: [55.273, 25.205], zoom: 11 }); });
question.addEventListener("input", updateComposer);
question.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!activeRequest) form.requestSubmit(); }
});
document.addEventListener("keydown", event => { if (event.key === "Escape") { closeSidebar(); } });
matchMedia("(max-width: 760px)").addEventListener("change", () => { closeSidebar(); });
for (const example of document.querySelectorAll("[data-question]")) {
  example.addEventListener("click", () => { question.value = example.dataset.question; form.requestSubmit(); });
}
form.addEventListener("submit", async event => {
  event.preventDefault(); const text = question.value.trim(); if (!text || activeRequest) return;
  let session = sessions.find(s => s.id === currentId);
  if (!session) { session = { id: crypto.randomUUID(), title: text, messages: [] }; sessions.unshift(session); sessions = sessions.slice(0, 20); currentId = session.id; }
  const userMessage = { role: "user", text }; session.messages.push(userMessage); renderMessage(userMessage); question.value = "";
  const controller = new AbortController(); activeRequest = controller; form.setAttribute("aria-busy", "true"); updateComposer(); save();
  const pending = renderMessage({ role: "assistant", text: "Exploring the Dubai sample…" }); pending.classList.add("pending"); scrollChat();
  const timeout = setTimeout(() => controller.abort("timeout"), 150000);
  try {
    const response = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: text }), signal: controller.signal });
    const data = await response.json().catch(() => { throw new Error("Chat is unavailable. Start the app server and try again."); });
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "We couldn’t complete that search. Please try again.");
    if (typeof data.answer !== "string" || !Array.isArray(data.features?.features)) throw new Error("The search returned an unexpected response. Please try again.");
    if (activeRequest !== controller) return;
    const message = { role: "assistant", text: data.answer, data }; session.messages.push(message); pending.remove(); renderMessage(message);
    if (!data.is_greeting) setMapData(data);
  } catch (error) {
    if (activeRequest !== controller) return;
    const message = { role: "assistant", error: true, text: controller.signal.aborted ? "This search took too long. Please try again." : error instanceof TypeError ? "Couldn’t reach the chat server. Check that the app is running and try again." : error.message };
    session.messages.push(message); pending.remove(); renderMessage(message);
  } finally {
    clearTimeout(timeout);
    if (activeRequest === controller) { activeRequest = null; form.removeAttribute("aria-busy"); updateComposer(); save(); scrollChat(); question.focus(); }
  }
});
    function updateMap() {
      if (!mapReady) return;
      const area = latest.search_area || empty;
      map.getSource("matches").setData(latest.features);
      map.getSource("search-area").setData(area);
      mapKey.hidden = latest.features.features.length === 0 && area.features.length === 0;
      areaKey.hidden = area.features.length === 0;

      const coordinates = latest.features.features.map(feature => feature.geometry.coordinates);
      for (const feature of area.features) {
        if (feature.geometry.type === "Polygon") coordinates.push(...feature.geometry.coordinates[0]);
      }
      if (coordinates.length === 0) return;
      const bounds = coordinates.reduce(
        ([minX, minY, maxX, maxY], [x, y]) =>
          [Math.min(minX, x), Math.min(minY, y), Math.max(maxX, x), Math.max(maxY, y)],
        [...coordinates[0], ...coordinates[0]]
      );
      map.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]], {
        padding: 45, maxZoom: 16, duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 450
      });
    }

    async function loadMap() {
      try {
        const maplibre = await import("https://unpkg.com/maplibre-gl@6.17.0/dist/maplibre-gl.mjs");
        map = new maplibre.Map({
          container: "map",
          style: "https://tiles.openfreemap.org/styles/liberty",
          center: [55.273, 25.205],
          zoom: 11
        });
        map.addControl(new maplibre.NavigationControl(), "top-right");
        map.on("error", () => {
          if (!mapReady) mapStatus.textContent = "The map could not load. Chat results are still available.";
        });
        map.on("load", () => {
          map.addSource("search-area", { type: "geojson", data: empty });
          map.addSource("matches", { type: "geojson", data: empty });
          map.addLayer({
            id: "search-fill", type: "fill", source: "search-area",
            paint: { "fill-color": "#e99a31", "fill-opacity": 0.17 }
          });
          map.addLayer({
            id: "search-outline", type: "line", source: "search-area",
            paint: { "line-color": "#a35a13", "line-width": 2, "line-dasharray": [2, 2] }
          });
          map.addLayer({
            id: "places", type: "circle", source: "matches",
            paint: { "circle-color": "#007b70", "circle-radius": 6, "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 }
          });
          map.addLayer({
            id: "landmark", type: "circle", source: "search-area",
            filter: ["==", ["geometry-type"], "Point"],
            paint: { "circle-color": "#d16b0e", "circle-radius": 8, "circle-stroke-color": "#fff", "circle-stroke-width": 2 }
          });
          map.on("click", "places", event => {
            const place = event.features[0];
            new maplibre.Popup()
              .setLngLat(place.geometry.coordinates)
              .setText(place.properties.POI_Name_English || "Place")
              .addTo(map);
          });
          map.on("click", "landmark", event => {
            const landmark = event.features[0];
            new maplibre.Popup()
              .setLngLat(landmark.geometry.coordinates)
              .setText(landmark.properties.name)
              .addTo(map);
          });
          mapReady = true;
          mapStatus.hidden = true;
          updateMap();
        });
      } catch (error) {
        mapStatus.textContent = "The map could not load. Chat results are still available.";
        console.error(error);
      }
    }


renderHistory(); syncSidebar(); loadMap();
new ResizeObserver(() => { if (map) map.resize(); }).observe($(".map-canvas"));
