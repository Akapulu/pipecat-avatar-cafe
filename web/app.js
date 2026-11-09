import Daily from "https://cdn.jsdelivr.net/npm/@daily-co/daily-js@0.93.0/+esm";

const app = document.querySelector("#app");
const banner = document.querySelector("#banner");
const video = document.querySelector("#avatar");
const status = document.querySelector("#status");
const fill = document.querySelector("#fill");
const loading = document.querySelector("#loading");
const startButton = document.querySelector("#start");
const endButton = document.querySelector("#end");

let call = null;
let audio = null;
let callReady = false;

function setPhase(phase) {
  app.className = `is-${phase}`;
}

function showBanner(text) {
  banner.hidden = !text;
  banner.textContent = text || "";
}

function setLoading(visible) {
  loading.hidden = !visible;
}

function setStatus(text) {
  status.textContent = text;
}

function setPercent(value) {
  const percent = Math.max(0, Math.min(100, Number(value) || 0));
  fill.style.width = `${percent}%`;
}

function statusBody(message) {
  if (!message || message.label !== "rtvi-ai" || message.type !== "server-message") {
    return null;
  }
  const data = message.data;
  if (!data || data.type !== "status") {
    return null;
  }
  return data;
}

function onAppMessage(event) {
  const message = event && event.data ? event.data : event;
  const body = statusBody(message);
  if (body) {
    if (typeof body.completion_percent === "number") {
      setPercent(body.completion_percent);
    }
    const text = body.latest_update_text;
    if (typeof text === "string" && text) {
      setStatus(text);
    }
    if (body.call_is_ready === true) {
      callReady = true;
      setPercent(100);
      setLoading(false);
      if (app.classList.contains("is-connecting")) {
        setStatus("Connected");
        setPhase("connected");
      }
    }
    return;
  }
  if (message && message.label === "cafe") {
    onCafeEvent(message);
  }
}

function onTrackStarted(event) {
  if (!event || !event.track || !event.participant || event.participant.local) {
    return;
  }
  if (event.participant.user_name !== "Avatar") {
    return;
  }
  if (event.track.kind === "video") {
    video.srcObject = new MediaStream([event.track]);
    video.play().catch(() => {
      setStatus("Select the page to play the video.");
    });
    if (callReady) {
      setLoading(false);
    }
  }
  if (event.track.kind === "audio") {
    if (!audio) {
      audio = new Audio();
      audio.autoplay = true;
    }
    audio.srcObject = new MediaStream([event.track]);
    audio.play().catch(() => {
      setStatus("Select the page to hear the audio.");
    });
  }
}

async function endCall() {
  const current = call;
  call = null;
  callReady = false;
  startButton.disabled = false;
  endButton.disabled = true;
  setLoading(false);
  setPhase("ended");
  if (current) {
    await current.leave();
    current.destroy();
  }
  video.srcObject = null;
  if (audio) {
    audio.srcObject = null;
  }
  setStatus("Call ended");
  showBanner("");
}

async function startCall() {
  startButton.disabled = true;
  endButton.disabled = true;
  callReady = false;
  resetOrder();
  setPhase("connecting");
  showBanner("");
  setLoading(true);
  setPercent(0);
  setStatus("Opening the room…");
  const response = await fetch("/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok || !body || typeof body !== "object") {
    const message = body && typeof body.error === "string" ? body.error : `Connect failed (${response.status}).`;
    setPhase("error");
    showBanner(message);
    setStatus(message);
    setLoading(false);
    startButton.disabled = false;
    return;
  }
  if (typeof body.room_url !== "string" || !body.room_url.startsWith("https://")) {
    setPhase("error");
    showBanner("Connect did not return a room url.");
    setStatus("Connect did not return a room url.");
    setLoading(false);
    startButton.disabled = false;
    return;
  }
  if (typeof body.token !== "string" || !body.token) {
    setPhase("error");
    showBanner("Connect did not return a token.");
    setStatus("Connect did not return a token.");
    setLoading(false);
    startButton.disabled = false;
    return;
  }
  call = Daily.createCallObject({
    videoSource: false,
    audioSource: true,
    subscribeToTracksAutomatically: true,
  });
  call.on("app-message", onAppMessage);
  call.on("track-started", onTrackStarted);
  call.on("left-meeting", () => {
    startButton.disabled = false;
    endButton.disabled = true;
    setLoading(false);
  });
  try {
    await call.join({
      url: body.room_url,
      token: body.token,
      userName: "You",
      startVideoOff: true,
      startAudioOff: false,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Daily join failed.";
    setPhase("error");
    showBanner(message);
    setStatus(message);
    await endCall();
    return;
  }
  endButton.disabled = false;
  setStatus("Joining the call…");
}

startButton.addEventListener("click", () => {
  startCall().catch((error) => {
    const message = error instanceof Error ? error.message : "Start failed.";
    setPhase("error");
    showBanner(message);
    setStatus(message);
    setLoading(false);
    startButton.disabled = false;
  });
});

endButton.addEventListener("click", () => {
  endCall().catch((error) => {
    const message = error instanceof Error ? error.message : "End failed.";
    setPhase("error");
    showBanner(message);
    setStatus(message);
  });
});

// ---- Cafe page: built from /menu.json, driven by the bot's "cafe" messages ----

const menuEl = document.querySelector("#menu");
const sectionsEl = document.querySelector("#sections");
const filtersEl = document.querySelector("#filters");
const orderLines = document.querySelector("#order-lines");
const orderEmpty = document.querySelector("#order-empty");
const orderTotal = document.querySelector("#order-total");
const placed = document.querySelector("#placed");
let menu = null;
let hotTimer = null;

const money = (n) => `$${Number(n).toFixed(2)}`;

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderMenu() {
  document.querySelector("#cafe-name").textContent = menu.cafe;
  for (const [id, title] of Object.entries(menu.sections)) {
    const link = el("a", "", title);
    link.href = `#section-${id}`;
    link.dataset.section = id;
    sectionsEl.append(link);

    const section = el("section", "menu-section");
    section.id = `section-${id}`;
    section.append(el("h2", "", title));
    const grid = el("div", "grid");
    for (const item of menu.items.filter((i) => i.section === id)) {
      const card = el("article", "item");
      card.id = `item-${item.id}`;
      card.dataset.tags = item.tags.join(" ");
      card.append(el("h3", "", item.name), el("span", "price", money(item.price)), el("p", "", item.about));
      const tags = el("div", "tags");
      for (const tag of item.tags) tags.append(el("span", "", menu.tags[tag]));
      card.append(tags);
      grid.append(card);
    }
    section.append(grid);
    menuEl.append(section);
  }
  for (const [id, label] of Object.entries({ all: "Everything", ...menu.tags })) {
    const chip = el("span", id === "all" ? "chip is-on" : "chip", label);
    chip.dataset.tag = id;
    filtersEl.append(chip);
  }
}

function showSection(id) {
  for (const link of sectionsEl.children) link.classList.toggle("is-active", link.dataset.section === id);
  document.querySelector(`#section-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function filterMenu(tag) {
  for (const chip of filtersEl.children) chip.classList.toggle("is-on", chip.dataset.tag === tag);
  for (const card of menuEl.querySelectorAll(".item")) {
    card.classList.toggle("is-dim", tag !== "all" && !card.dataset.tags.split(" ").includes(tag));
  }
}

function highlight(id) {
  for (const card of menuEl.querySelectorAll(".item.is-hot")) card.classList.remove("is-hot");
  const card = document.querySelector(`#item-${id}`);
  if (!card) return;
  card.classList.add("is-hot");
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  clearTimeout(hotTimer);
  hotTimer = setTimeout(() => card.classList.remove("is-hot"), 4000);
}

function renderOrder(lines, total) {
  orderLines.replaceChildren();
  for (const badge of menuEl.querySelectorAll(".badge")) badge.remove();
  const byId = Object.fromEntries(menu.items.map((i) => [i.id, i]));
  for (const [id, qty] of Object.entries(lines)) {
    const item = byId[id];
    const li = el("li");
    li.append(el("span", "", `${qty} × ${item.name}`), el("span", "", money(item.price * qty)));
    orderLines.append(li);
    document.querySelector(`#item-${id}`)?.append(el("span", "badge", qty));
  }
  orderEmpty.hidden = orderLines.children.length > 0;
  orderTotal.textContent = money(total);
}

function resetOrder() {
  if (!menu) return;
  renderOrder({}, 0);
  filterMenu("all");
  placed.hidden = true;
}

function onCafeEvent(msg) {
  if (msg.event === "section") showSection(msg.section);
  if (msg.event === "filter") filterMenu(msg.tag);
  if (msg.event === "highlight") highlight(msg.item_id);
  if (msg.event === "order") renderOrder(msg.lines, msg.total);
  if (msg.event === "placed") {
    placed.hidden = false;
    placed.textContent = `Order placed for ${msg.name}. Ready in about ${msg.ready_minutes} minutes. ☕`;
  }
}

fetch("/menu.json")
  .then((r) => r.json())
  .then((data) => {
    menu = data;
    renderMenu();
    resetOrder();
  });

// Lets a local test replay bot events without a live call.
window.cafeEvent = onCafeEvent;
