const API = window.location.port === "8000" ? "/api" : "http://127.0.0.1:8000/api";
let token = localStorage.getItem("campusToken");
let mode = "admin-login";
let events = [];
let currentUser;
let pendingPayment;
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
    pendingPayment = await request("/payments/create-demo-payment", { method:"POST", body:JSON.stringify({ event_id:id }) });
    $("demoPaymentSummary").textContent = `${pendingPayment.event.event_name} · ${pendingPayment.currency} ${pendingPayment.amount.toFixed(2)} · Reference ${pendingPayment.payment_reference}`;
    $("demoPaymentStatus").textContent = "Choose a simulated result. This is not a real payment.";
    $("demoPaymentModal").classList.remove("hidden");
  } catch (error) { toast(error.message); }
}
async function simulatePayment(outcome) {
  if (!pendingPayment) return;
  $("simulateSuccess").disabled = true; $("simulateFailure").disabled = true;
  try {
    const payment = await request("/payments/simulate", { method:"POST", body:JSON.stringify({ payment_id:pendingPayment.payment_id, outcome }) });
    toast(payment.payment_status === "Successful" ? "Payment successful. Booking confirmed." : "Payment failed. You can retry.");
    closeDemoPayment(); await loadEvents(); await loadBookings(); await loadPayments();
  } catch (error) {
    $("demoPaymentStatus").textContent = error.message;
    $("simulateSuccess").disabled = false; $("simulateFailure").disabled = false;
  }
}
function closeDemoPayment() { pendingPayment = null; $("demoPaymentModal").classList.add("hidden"); $("simulateSuccess").disabled = false; $("simulateFailure").disabled = false; }
async function loadBookings() {
  const bookings = await request("/participant/bookings");
  $("bookingList").innerHTML = bookings.length ? bookings.map((booking) => `<div class="booking"><strong>${escapeHtml(booking.booking_reference)}</strong><span>${escapeHtml(booking.event.event_name)} · ${escapeHtml(booking.college.college_name)} · ${escapeHtml(booking.booking_status)}</span></div>`).join("") : "<p class='muted'>No bookings yet.</p>";
}
async function loadPayments() {
  const payments = await request("/payments/my-payments");
  $("paymentList").innerHTML = payments.length ? payments.map((payment) => `<div class="booking"><strong>${escapeHtml(payment.event.event_name)}</strong><span>${escapeHtml(payment.payment_reference)} · ₹${payment.amount} · ${escapeHtml(payment.payment_status)} ${payment.payment_status === "Successful" ? `<a class="button outline" href="#" onclick="downloadPdf('/participant/receipts/${payment.id}/download', 'payment-receipt-${payment.id}.pdf'); return false;">Download receipt</a>` : ""}</span></div>`).join("") : "<p class='muted'>No payments yet.</p>";
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
  $("adminEvents").innerHTML = adminEvents.length ? adminEvents.map((event) => `<div class="admin-event"><span><strong>${escapeHtml(event.event_name)}</strong><small>${escapeHtml(event.event_date)} · ${escapeHtml(event.event_time)} · ${escapeHtml(event.duration)} · ${event.available_seats}/${event.maximum_seats} seats</small></span><button class="button outline" onclick="editEvent(${event.id})">Edit</button><button class="button outline" onclick="participants(${event.id})">Participants</button><button class="button outline" onclick="downloadPdf('/admin/events/${event.id}/participants/pdf', 'participants-${event.id}.pdf'); return false;">Download participants PDF</button><button class="button danger" onclick="removeEvent(${event.id})">Delete</button></div>`).join("") : "<p class='muted'>No events available at the moment.</p>";
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
$("closeDemoPayment").addEventListener("click", closeDemoPayment); $("simulateSuccess").addEventListener("click", () => simulatePayment("successful")); $("simulateFailure").addEventListener("click", () => simulatePayment("failed"));
$("cancelEdit").addEventListener("click", () => { $("eventForm").reset(); $("eventId").value = ""; $("cancelEdit").classList.add("hidden"); });
["eventSearch","category","eventDate"].forEach((id) => $(id).addEventListener("change", loadEvents));
if (token) loadDashboard();
