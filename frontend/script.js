const API = window.location.port === "8000" ? "/api" : "http://127.0.0.1:8000/api";
let token = localStorage.getItem("campusToken");
let mode = "admin-login";
let events = [];
let currentUser;
const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[char]));

async function request(path, options = {}) {
  const headers = { "Content-Type":"application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join(", ") : data.detail || "Request failed.");
  return data;
}

function toast(message) { $("toast").textContent = message; $("toast").classList.add("show"); setTimeout(() => $("toast").classList.remove("show"), 3500); }
function setMode(next) {
  mode = next;
  const admin = mode.startsWith("admin");
  const register = mode.endsWith("register");
  $("authTitle").textContent = `${admin ? "Admin" : "Participant"} ${register ? "registration" : "login"}`;
  $("authSwitch").textContent = register ? "Already registered? Log in" : "First time here? Register";
  $("fullNameField").classList.toggle("hidden", !register);
  $("collegeFields").classList.toggle("hidden", !(admin && register));
  $("studentCollegeField").classList.toggle("hidden", !(register && !admin));
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.mode.startsWith(admin ? "admin" : "participant")));
  $("authError").textContent = ""; $("authSuccess").textContent = "";
}
function openAuth(next) { setMode(next); $("modal").classList.remove("hidden"); }
async function authSubmit(event) {
  event.preventDefault();
  const admin = mode.startsWith("admin"); const register = mode.endsWith("register");
  const body = { email: $("email").value, password: $("password").value };
  if (register) body.full_name = $("fullName").value;
  if (admin && register) body.college = { college_name: $("collegeName").value, college_location: $("collegeLocation").value };
  if (!admin && register) body.college_name = $("studentCollege").value;
  try {
    const result = await request(`/${admin ? "admin" : "participant"}/${register ? "register" : "login"}`, { method:"POST", body:JSON.stringify(body) });
    if (register) { setMode(admin ? "admin-login" : "participant-login"); $("email").value = body.email; $("password").value = ""; $("authSuccess").textContent = `${admin ? "Admin" : "Participant"} registered successfully. Use your email and password to log in.`; return; }
    token = result.access_token; localStorage.setItem("campusToken", token); $("modal").classList.add("hidden"); await loadDashboard();
  } catch (error) { $("authError").textContent = error.message; }
}
async function loadDashboard() {
  try {
    currentUser = await request("/auth/me"); $("home").classList.add("hidden"); $("logout").classList.remove("hidden");
    if (currentUser.role === "admin") { $("adminDashboard").classList.remove("hidden"); const profile = await request("/admin/profile"); $("adminCollege").textContent = `${profile.college.college_name} dashboard`; await loadAdminEvents(); }
    else { $("participantDashboard").classList.remove("hidden"); await loadEvents(); await loadBookings(); await loadPayments(); }
  } catch { logout(false); }
}
async function loadEvents() {
  const params = new URLSearchParams();
  if ($("eventSearch").value) params.set("search", $("eventSearch").value);
  if ($("category").value) params.set("category", $("category").value);
  if ($("eventDate").value) params.set("event_date", $("eventDate").value);
  const result = await request(`/events?${params}`); events = result;
  const categories = [...new Set(events.map((event) => event.category))];
  $("category").innerHTML = `<option value="">All categories</option>${categories.map((item) => `<option>${escapeHtml(item)}</option>`).join("")}`;
  $("eventList").innerHTML = events.length ? events.map((event) => `<article class="event-card"><span class="event-tag">${escapeHtml(event.category)}</span><h3>${escapeHtml(event.event_name)}</h3><p><strong>${escapeHtml(event.college_name || "Campus event")}</strong><br>${escapeHtml(event.event_date)} · ${escapeHtml(event.event_time)} · ${escapeHtml(event.duration)}<br>${escapeHtml(event.venue)}</p><p class="muted">${escapeHtml(event.description)}</p><strong>${event.registration_fee ? `₹${event.registration_fee}` : "Free"}</strong><span class="availability">${event.available_seats} seats available</span><button class="button primary" onclick="book(${event.id})">Book now</button></article>`).join("") : "<p class='muted'>No events available at the moment.</p>";
}
async function book(id) {
  const event = events.find((item) => item.id === id);
  if (!event) return;
  if (!event.registration_fee) {
    try { await request(`/events/${id}/book`, { method:"POST" }); toast("Booking confirmed."); await loadEvents(); await loadBookings(); } catch (error) { toast(error.message); }
    return;
  }
  try {
    const order = await request("/payments/create-order", { method:"POST", body:JSON.stringify({ event_id:id }) });
    if (!window.Razorpay) throw new Error("Razorpay Checkout could not be loaded.");
    const checkout = new Razorpay({
      key: order.key_id, amount: order.amount_paise, currency: order.currency, name: "Campus Event Ticketing Engine",
      description: order.event.event_name, order_id: order.order_id,
      handler: async (result) => {
        try {
          await request("/payments/verify", { method:"POST", body:JSON.stringify(result) });
          toast("Payment successful. Booking confirmed."); await loadEvents(); await loadBookings(); await loadPayments();
        } catch (error) { toast(error.message); }
      },
      modal: { ondismiss: async () => { try { await request("/payments/fail", { method:"POST", body:JSON.stringify({ razorpay_order_id:order.order_id }) }); toast("Payment cancelled. You can retry safely."); } catch (error) { toast(`Payment cancellation could not be recorded: ${error.message}`); } } },
      prefill: { name: currentUser.full_name }
    });
    checkout.open();
  } catch (error) { toast(error.message); }
}
async function loadBookings() {
  const bookings = await request("/participant/bookings");
  $("bookingList").innerHTML = bookings.length ? bookings.map((booking) => `<div class="booking"><strong>${escapeHtml(booking.booking_reference)}</strong><span>${escapeHtml(booking.event.event_name)} · ${escapeHtml(booking.college.college_name)} · ${escapeHtml(booking.booking_status)}</span></div>`).join("") : "<p class='muted'>No bookings yet.</p>";
}
async function loadPayments() {
  const payments = await request("/payments/my-payments");
  $("paymentList").innerHTML = payments.length ? payments.map((payment) => `<div class="booking"><strong>${escapeHtml(payment.event.event_name)}</strong><span>${escapeHtml(payment.gateway_payment_id || "Pending")} · ₹${payment.amount} · ${escapeHtml(payment.payment_status)} ${payment.payment_status === "Successful" ? `<a class="button outline" href="#" onclick="downloadPdf('/participant/receipts/${payment.id}/download', 'payment-receipt-${payment.id}.pdf'); return false;">Download receipt</a>` : ""}</span></div>`).join("") : "<p class='muted'>No payments yet.</p>";
}
async function downloadPdf(path, filename) {
  try {
    const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || "Download failed."); }
    const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a");
    link.href = url; link.download = filename; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
  } catch (error) { toast(error.message); }
}
async function loadAdminEvents() {
  const adminEvents = await request("/admin/events");
  $("adminEvents").innerHTML = adminEvents.length ? adminEvents.map((event) => `<div class="admin-event"><span><strong>${escapeHtml(event.event_name)}</strong><small>${escapeHtml(event.event_date)} · ${escapeHtml(event.event_time)} · ${escapeHtml(event.duration)} · ${event.available_seats}/${event.maximum_seats} seats</small></span><button class="button outline" onclick="editEvent(${event.id})">Edit</button><button class="button outline" onclick="participants(${event.id})">Participants</button><button class="button danger" onclick="removeEvent(${event.id})">Delete</button></div>`).join("") : "<p class='muted'>No events available at the moment.</p>";
}
async function editEvent(id) { const event = await request(`/admin/events/${id}`); $("eventId").value = id; $("eventName").value = event.event_name; $("description").value = event.description; $("eventDateAdmin").value = event.event_date; $("eventTime").value = event.event_time; $("duration").value = event.duration; $("venue").value = event.venue; $("eventCategory").value = event.category; $("fee").value = event.registration_fee; $("maximumSeats").value = event.maximum_seats; $("cancelEdit").classList.remove("hidden"); }
async function saveEvent(event) { event.preventDefault(); const id = $("eventId").value; const body = { event_name:$("eventName").value, description:$("description").value, event_date:$("eventDateAdmin").value, event_time:$("eventTime").value, duration:$("duration").value, venue:$("venue").value, category:$("eventCategory").value, registration_fee:Number($("fee").value), maximum_seats:Number($("maximumSeats").value) }; try { await request(`/admin/events${id ? `/${id}` : ""}`, { method:id ? "PUT" : "POST", body:JSON.stringify(body) }); $("eventForm").reset(); $("eventId").value = ""; $("cancelEdit").classList.add("hidden"); toast("Event published."); loadAdminEvents(); } catch (error) { toast(error.message); } }
async function removeEvent(id) { if (!confirm("Delete this event? Its booking history will be retained.")) return; try { await request(`/admin/events/${id}`, { method:"DELETE" }); toast("Event deleted."); loadAdminEvents(); } catch (error) { toast(error.message); } }
async function participants(id) {
  try {
    const report = await request(`/admin/events/${id}/participants`);
    $("participants").innerHTML = `<h2>Participants: ${escapeHtml(report.event.event_name)}</h2><a class="button outline" href="#" onclick="downloadPdf('/admin/events/${id}/participants/pdf', 'participants-${id}.pdf'); return false;">Download participant list PDF</a>${report.participants.length ? report.participants.map((item, index) => `<div class="booking"><strong>${index + 1}. ${escapeHtml(item.student_name)}</strong><span>${escapeHtml(item.student_email)} · ${escapeHtml(item.booking_reference)} · ${escapeHtml(item.payment_status)} · ₹${item.payment_amount}</span></div>`).join("") : "<p class='muted'>No participants yet.</p>"}`;
  } catch (error) { toast(error.message); }
}
function logout(show = true) { token = null; currentUser = null; localStorage.removeItem("campusToken"); $("home").classList.remove("hidden"); $("participantDashboard").classList.add("hidden"); $("adminDashboard").classList.add("hidden"); $("logout").classList.add("hidden"); if (show) toast("Logged out."); }
document.querySelectorAll(".auth-option").forEach((button) => button.addEventListener("click", () => openAuth(button.dataset.mode)));
document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
$("authSwitch").addEventListener("click", () => setMode(`${mode.startsWith("admin") ? "admin" : "participant"}-${mode.endsWith("register") ? "login" : "register"}`));
$("authForm").addEventListener("submit", authSubmit); $("closeModal").addEventListener("click", () => $("modal").classList.add("hidden")); $("logout").addEventListener("click", () => logout()); $("eventForm").addEventListener("submit", saveEvent);
$("cancelEdit").addEventListener("click", () => { $("eventForm").reset(); $("eventId").value = ""; $("cancelEdit").classList.add("hidden"); });
["eventSearch","category","eventDate"].forEach((id) => $(id).addEventListener("change", loadEvents));
if (token) loadDashboard();
