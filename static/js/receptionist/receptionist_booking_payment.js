const API_BASE_URL = window.location.origin;
const accessToken = localStorage.getItem("access_token");
const currentUser = JSON.parse(localStorage.getItem("current_user") || "null");

/* =========================
   DOM TOPBAR
========================= */
const logoutBtn = document.getElementById("logoutBtn");
const receptionistNameBadge = document.getElementById("receptionistNameBadge");

/* =========================
   DOM HOTEL INFO
========================= */
const hotelNameText = document.getElementById("hotelNameText");
const hotelAddressText = document.getElementById("hotelAddressText");

/* =========================
   DOM BOOKING FILTER
========================= */
const bookingFilterForm = document.getElementById("bookingFilterForm");
const fromDateInput = document.getElementById("fromDateInput");
const toDateInput = document.getElementById("toDateInput");
const bookingStatusInput = document.getElementById("bookingStatusInput");
const paymentStatusInput = document.getElementById("paymentStatusInput");
const bookingKeywordInput = document.getElementById("bookingKeywordInput");
const resetBookingFilterBtn = document.getElementById("resetBookingFilterBtn");
const dateFilterError = document.getElementById("dateFilterError");

/* =========================
   DOM BOOKING TABLE
========================= */
const bookingTableBody = document.getElementById("bookingTableBody");
const bookingResultCount = document.getElementById("bookingResultCount");
const bookingPaginationWrap = document.getElementById("bookingPaginationWrap");
const bookingPaginationNumbers = document.getElementById("bookingPaginationNumbers");
const bookingPrevPageBtn = document.getElementById("bookingPrevPageBtn");
const bookingNextPageBtn = document.getElementById("bookingNextPageBtn");

/* =========================
   DOM PAYMENT FILTER
========================= */
const paymentFilterForm = document.getElementById("paymentFilterForm");
const paymentKeywordInput = document.getElementById("paymentKeywordInput");
const paymentStatusFilterInput = document.getElementById("paymentStatusFilterInput");
const resetPaymentFilterBtn = document.getElementById("resetPaymentFilterBtn");

/* =========================
   DOM PAYMENT TABLE
========================= */
const paymentTableBody = document.getElementById("paymentTableBody");
const paymentResultCount = document.getElementById("paymentResultCount");
const paymentPaginationWrap = document.getElementById("paymentPaginationWrap");
const paymentPaginationNumbers = document.getElementById("paymentPaginationNumbers");
const paymentPrevPageBtn = document.getElementById("paymentPrevPageBtn");
const paymentNextPageBtn = document.getElementById("paymentNextPageBtn");

/* =========================
   DOM TABS
========================= */
const showBookingTabBtn = document.getElementById("showBookingTabBtn");
const showPaymentTabBtn = document.getElementById("showPaymentTabBtn");
const bookingTab = document.getElementById("bookingTab");
const paymentTab = document.getElementById("paymentTab");

/* =========================
   DOM DETAIL MODAL
========================= */
const detailOverlay = document.getElementById("detailOverlay");
const closeDetailBtn = document.getElementById("closeDetailBtn");
const detailPaymentChip = document.getElementById("detailPaymentChip");
const detailBookingInfo = document.getElementById("detailBookingInfo");
const checkInBtn = document.getElementById("checkInBtn");
const checkOutBtn = document.getElementById("checkOutBtn");
const cancelBookingBtn = document.getElementById("cancelBookingBtn");

/* =========================
   DOM CONFIRM + TOAST
========================= */
const confirmOverlay = document.getElementById("confirmOverlay");
const confirmMessage = document.getElementById("confirmMessage");
const confirmCancelBtn = document.getElementById("confirmCancelBtn");
const confirmOkBtn = document.getElementById("confirmOkBtn");
const toast = document.getElementById("toast");

/* =========================
   STATE
========================= */
let currentHotelInfo = null;

let bookingResults = [];
let paymentResults = [];
let filteredPayments = [];
let currentBooking = null;

let bookingCurrentPage = 1;
let paymentCurrentPage = 1;

const BOOKING_PAGE_SIZE = 10;
const PAYMENT_PAGE_SIZE = 10;

/* =========================
   AUTH
========================= */
function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${accessToken}`
  };
}

function ensureReceptionistAccess() {
  if (!accessToken || !currentUser) {
    window.location.href = "/auth-page";
    return false;
  }

  if (currentUser.role_name !== "Receptionist") {
    window.location.href = "/user-info-page";
    return false;
  }

  return true;
}

async function fetchWithAuth(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.headers || {})
    }
  });

  if (response.status === 401 || response.status === 403) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("current_user");
    window.location.href = "/auth-page";
    throw new Error("Phiên đăng nhập đã hết hạn hoặc bạn không có quyền truy cập.");
  }

  return response;
}

/* =========================
   HELPERS
========================= */
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (Number.isNaN(num)) return "—";
  return num.toLocaleString("vi-VN") + " VND";
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("vi-VN");
}

function getStatusChipClass(status) {
  const raw = String(status || "").trim().toLowerCase();

  if (raw === "paid" || raw === "confirmed") {
    return "status-chip success";
  }

  if (raw === "cancelled") {
    return "status-chip danger";
  }

  // unpaid / pending / not paid
  return "status-chip warning";
}

function showToast(message, type = "info") {
  if (!toast) {
    alert(message);
    return;
  }

  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.classList.remove("hidden");

  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => {
    toast.classList.add("hidden");
  }, 3200);
}

function renderHotelInfo() {
  if (hotelNameText) {
    hotelNameText.textContent = currentHotelInfo?.hotel_name || "Đang cập nhật";
  }

  if (hotelAddressText) {
    hotelAddressText.textContent = currentHotelInfo?.address || "Đang cập nhật";
  }
}

/* =========================
   CONFIRM MODAL
========================= */
function openConfirmModal(message, onConfirm) {
  confirmMessage.textContent = message;
  confirmOverlay.classList.remove("hidden");

  confirmOkBtn.onclick = () => {
    closeConfirmModal();
    onConfirm();
  };

  confirmCancelBtn.onclick = () => {
    closeConfirmModal();
  };
}

function closeConfirmModal() {
  confirmOverlay.classList.add("hidden");
  confirmOkBtn.onclick = null;
  confirmCancelBtn.onclick = null;
}

/* =========================
   DATE VALIDATION
========================= */
function showDateFilterError(message) {
  if (dateFilterError) {
    dateFilterError.textContent = message;
    dateFilterError.classList.remove("hidden");
  }

  fromDateInput?.classList.add("input-error");
  toDateInput?.classList.add("input-error");
}

function hideDateFilterError() {
  if (dateFilterError) {
    dateFilterError.classList.add("hidden");
  }

  fromDateInput?.classList.remove("input-error");
  toDateInput?.classList.remove("input-error");
}

/* =========================
   LOGOUT
========================= */
function handleLogout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("current_user");
  window.location.href = "/auth-page";
}

/* =========================
   TAB SWITCH
========================= */
function showBookingTab() {
  bookingTab.classList.remove("hidden");
  paymentTab.classList.add("hidden");
  showBookingTabBtn.classList.add("active");
  showPaymentTabBtn.classList.remove("active");
}

function showPaymentTab() {
  paymentTab.classList.remove("hidden");
  bookingTab.classList.add("hidden");
  showPaymentTabBtn.classList.add("active");
  showBookingTabBtn.classList.remove("active");
}

/* =========================
   LOAD BOOKINGS
========================= */
async function loadBookings(event) {
  if (event) event.preventDefault();

  const fromDate = fromDateInput.value || "";
  const toDate = toDateInput.value || "";

  hideDateFilterError();

  // Điều kiện user yêu cầu:
  // nếu filter cả 2 ngày thì check-out phải lớn hơn check-in
  if (fromDate && toDate && toDate <= fromDate) {
    showDateFilterError("Nếu nhập cả 2 ngày, ngày check-out phải lớn hơn ngày check-in.");
    bookingResults = [];
    bookingTableBody.innerHTML = `
      <tr>
        <td colspan="9" class="table-empty">Vui lòng kiểm tra lại bộ lọc ngày.</td>
      </tr>
    `;
    bookingResultCount.textContent = "0 kết quả";
    bookingPaginationWrap.classList.add("hidden");
    return;
  }

  bookingTableBody.innerHTML = `
    <tr>
      <td colspan="9" class="table-empty">Đang tải dữ liệu...</td>
    </tr>
  `;

  const params = new URLSearchParams();
  if (fromDate) params.append("from_date", fromDate);
  if (toDate) params.append("to_date", toDate);
  if (bookingStatusInput.value) params.append("booking_status", bookingStatusInput.value);
  if (paymentStatusInput.value) params.append("payment_status", paymentStatusInput.value);
  if (bookingKeywordInput.value.trim()) params.append("keyword", bookingKeywordInput.value.trim());

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/receptionist/bookings?${params.toString()}`, {
      method: "GET"
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không tải được danh sách booking.");
    }

    currentHotelInfo = data?.hotel || null;
    renderHotelInfo();

    bookingResults = Array.isArray(data?.data) ? data.data : [];
    bookingCurrentPage = 1;

    renderBookingTable();
    renderBookingPagination();
  } catch (error) {
    console.error("loadBookings error:", error);
    bookingTableBody.innerHTML = `
      <tr>
        <td colspan="9" class="table-empty">Không tải được danh sách booking.</td>
      </tr>
    `;
    bookingResultCount.textContent = "0 kết quả";
    bookingPaginationWrap.classList.add("hidden");

    if (hotelNameText) hotelNameText.textContent = "Không tải được";
    if (hotelAddressText) hotelAddressText.textContent = "Không tải được";

    showToast(error.message || "Không tải được booking.", "error");
  }
}

/* =========================
   LOAD PAYMENTS
========================= */
async function loadPayments() {
  paymentTableBody.innerHTML = `
    <tr>
      <td colspan="7" class="table-empty">Đang tải dữ liệu...</td>
    </tr>
  `;

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/receptionist/bookings/payments/all`, {
      method: "GET"
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không tải được danh sách payment.");
    }

    if (!currentHotelInfo && data?.hotel) {
      currentHotelInfo = data.hotel;
      renderHotelInfo();
    }

    paymentResults = Array.isArray(data?.data) ? data.data : [];
    applyPaymentFilters();
  } catch (error) {
    console.error("loadPayments error:", error);
    paymentTableBody.innerHTML = `
      <tr>
        <td colspan="7" class="table-empty">Không tải được danh sách payment.</td>
      </tr>
    `;
    paymentResultCount.textContent = "0 kết quả";
    paymentPaginationWrap.classList.add("hidden");
    showToast(error.message || "Không tải được payment.", "error");
  }
}

/* =========================
   BOOKING PAGINATION
========================= */
function getPaginatedBookings() {
  const start = (bookingCurrentPage - 1) * BOOKING_PAGE_SIZE;
  const end = start + BOOKING_PAGE_SIZE;
  return bookingResults.slice(start, end);
}

function renderBookingPagination() {
  const totalPages = Math.ceil(bookingResults.length / BOOKING_PAGE_SIZE);

  if (totalPages <= 1) {
    bookingPaginationWrap.classList.add("hidden");
    return;
  }

  bookingPaginationWrap.classList.remove("hidden");
  bookingPaginationNumbers.innerHTML = "";

  for (let i = 1; i <= totalPages; i++) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `page-btn ${i === bookingCurrentPage ? "active" : ""}`;
    btn.textContent = i;

    btn.addEventListener("click", () => {
      bookingCurrentPage = i;
      renderBookingTable();
      renderBookingPagination();
    });

    bookingPaginationNumbers.appendChild(btn);
  }

  bookingPrevPageBtn.disabled = bookingCurrentPage === 1;
  bookingNextPageBtn.disabled = bookingCurrentPage === totalPages;
}

/* =========================
   PAYMENT PAGINATION
========================= */
function getPaginatedPayments() {
  const start = (paymentCurrentPage - 1) * PAYMENT_PAGE_SIZE;
  const end = start + PAYMENT_PAGE_SIZE;
  return filteredPayments.slice(start, end);
}

function renderPaymentPagination() {
  const totalPages = Math.ceil(filteredPayments.length / PAYMENT_PAGE_SIZE);

  if (totalPages <= 1) {
    paymentPaginationWrap.classList.add("hidden");
    return;
  }

  paymentPaginationWrap.classList.remove("hidden");
  paymentPaginationNumbers.innerHTML = "";

  for (let i = 1; i <= totalPages; i++) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `page-btn ${i === paymentCurrentPage ? "active" : ""}`;
    btn.textContent = i;

    btn.addEventListener("click", () => {
      paymentCurrentPage = i;
      renderPaymentTable();
      renderPaymentPagination();
    });

    paymentPaginationNumbers.appendChild(btn);
  }

  paymentPrevPageBtn.disabled = paymentCurrentPage === 1;
  paymentNextPageBtn.disabled = paymentCurrentPage === totalPages;
}

/* =========================
   RENDER BOOKING TABLE
========================= */
function renderBookingTable() {
  bookingResultCount.textContent = `${bookingResults.length} kết quả`;

  const currentItems = getPaginatedBookings();

  if (!currentItems.length) {
    bookingTableBody.innerHTML = `
      <tr>
        <td colspan="9" class="table-empty">Không có booking phù hợp.</td>
      </tr>
    `;
    return;
  }

  bookingTableBody.innerHTML = currentItems.map(item => `
    <tr>
      <td>${escapeHtml(item.booking_id)}</td>
      <td>${escapeHtml(item.booking_code || "—")}</td>
      <td>
        <strong>${escapeHtml(item.customer_name || "—")}</strong><br />
        <span>${escapeHtml(item.email || "—")}</span>
      </td>
      <td>${escapeHtml(formatDate(item.check_in))}</td>
      <td>${escapeHtml(formatDate(item.check_out))}</td>
      <td>${escapeHtml(formatMoney(item.total_amount))}</td>
      <td>
        <span class="${getStatusChipClass(item.booking_status)}">
          ${escapeHtml(item.booking_status || "—")}
        </span>
      </td>
      <td>
        <span class="${getStatusChipClass(item.payment_status)}">
          ${escapeHtml(item.payment_status || "—")}
        </span>
      </td>
      <td>
        <button class="view-btn booking-detail-btn" data-booking-id="${item.booking_id}" type="button">
          Xem chi tiết
        </button>
      </td>
    </tr>
  `).join("");

  bookingTableBody.querySelectorAll(".booking-detail-btn").forEach(btn => {
    btn.addEventListener("click", () => openBookingDetail(Number(btn.dataset.bookingId)));
  });
}

/* =========================
   PAYMENT FILTER + RENDER
========================= */
function normalizePaymentStatus(value) {
  const raw = String(value || "").trim().toLowerCase();

  if (raw === "paid") return "paid";

  // gom các trạng thái chưa thanh toán về 1 nhóm
  if (raw === "unpaid" || raw === "pending" || raw === "notpaid" || raw === "not paid") {
    return "unpaid";
  }

  return raw;
}

function applyPaymentFilters(event) {
  if (event) event.preventDefault();

  const keyword = (paymentKeywordInput.value || "").trim().toLowerCase();
  const selectedPaymentStatus = normalizePaymentStatus(paymentStatusFilterInput.value || "");

  filteredPayments = paymentResults.filter(item => {
    const matchKeyword =
      !keyword ||
      String(item.customer_name || "").toLowerCase().includes(keyword) ||
      String(item.booking_code || "").toLowerCase().includes(keyword);

    const itemPaymentStatus = normalizePaymentStatus(item.payment_status || "");

    const matchStatus =
      !selectedPaymentStatus ||
      itemPaymentStatus === selectedPaymentStatus;

    return matchKeyword && matchStatus;
  });

  paymentCurrentPage = 1;
  renderPaymentTable();
  renderPaymentPagination();
}

function renderPaymentTable() {
  paymentResultCount.textContent = `${filteredPayments.length} kết quả`;

  const currentItems = getPaginatedPayments();

  if (!currentItems.length) {
    paymentTableBody.innerHTML = `
      <tr>
        <td colspan="7" class="table-empty">Không có payment phù hợp.</td>
      </tr>
    `;
    return;
  }

  paymentTableBody.innerHTML = currentItems.map(item => `
    <tr>
      <td>${escapeHtml(item.payment_id)}</td>
      <td>${escapeHtml(item.booking_code || "—")}</td>
      <td>${escapeHtml(item.customer_name || "—")}</td>
      <td>${escapeHtml(formatMoney(item.amount))}</td>
      <td>${escapeHtml(item.payment_method || "—")}</td>
      <td>
        <span class="${getStatusChipClass(item.payment_status)}">
          ${escapeHtml(item.payment_status || "—")}
        </span>
      </td>
      <td>${escapeHtml(formatDate(item.paid_at))}</td>
    </tr>
  `).join("");
}

/* =========================
   BOOKING DETAIL
========================= */
async function openBookingDetail(bookingId) {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/receptionist/bookings/${bookingId}`, {
      method: "GET"
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không tải được chi tiết booking.");
    }

    currentBooking = data;
    fillBookingDetail(data);
    detailOverlay.classList.remove("hidden");
  } catch (error) {
    console.error("openBookingDetail error:", error);
    showToast(error.message || "Không tải được chi tiết booking.", "error");
  }
}

function fillBookingDetail(item) {
  detailPaymentChip.textContent = item.payment_status || "—";
  detailPaymentChip.className = getStatusChipClass(item.payment_status);

  const bookingStatus = String(item.booking_status || "").trim().toLowerCase();
  const actualCheckInTime = item.actual_check_in_time || null;
  const actualCheckOutTime = item.actual_check_out_time || null;

  const isCheckedIn = actualCheckInTime !== null;
  const isCheckedOut = actualCheckOutTime !== null;
  const isCancelled = bookingStatus === "cancelled";

  // KHÔNG disable nút nữa để user bấm lần 2 vẫn nhận được message từ backend
  checkInBtn.disabled = false;
  checkOutBtn.disabled = false;
  cancelBookingBtn.disabled = false;

  // Đổi text nút cho dễ hiểu trạng thái hiện tại
  checkInBtn.textContent = isCheckedIn ? "Đã check-in" : "Check-in";
  checkOutBtn.textContent = isCheckedOut ? "Đã check-out" : "Check-out";
  cancelBookingBtn.textContent = isCancelled ? "Đã hủy booking" : "Hủy booking";

  detailBookingInfo.innerHTML = `
    <div class="detail-item">
      <span>Booking ID</span>
      <strong>${escapeHtml(item.booking_id ?? "—")}</strong>
    </div>

    <div class="detail-item">
      <span>Mã booking</span>
      <strong>${escapeHtml(item.booking_code || "—")}</strong>
    </div>

    <div class="detail-item">
      <span>Khách hàng</span>
      <strong>${escapeHtml(item.customer_name || "—")}</strong>
    </div>

    <div class="detail-item">
      <span>Email</span>
      <strong>${escapeHtml(item.email || "—")}</strong>
    </div>

    <div class="detail-item">
      <span>Số điện thoại</span>
      <strong>${escapeHtml(item.phone || "—")}</strong>
    </div>

    <div class="detail-item">
      <span>Khách sạn</span>
      <strong>${escapeHtml(item.hotel_name || "—")}</strong>
    </div>

    <div class="detail-item">
      <span>Check-in dự kiến</span>
      <strong>${escapeHtml(formatDate(item.check_in))}</strong>
    </div>

    <div class="detail-item">
      <span>Check-out dự kiến</span>
      <strong>${escapeHtml(formatDate(item.check_out))}</strong>
    </div>

    <div class="detail-item">
      <span>Check-in thực tế</span>
      <strong>${escapeHtml(formatDate(item.actual_check_in_time))}</strong>
    </div>

    <div class="detail-item">
      <span>Check-out thực tế</span>
      <strong>${escapeHtml(formatDate(item.actual_check_out_time))}</strong>
    </div>

    <div class="detail-item">
      <span>Tổng tiền</span>
      <strong>${escapeHtml(formatMoney(item.total_amount))}</strong>
    </div>

    <div class="detail-item">
      <span>Trạng thái booking</span>
      <strong>${escapeHtml(item.booking_status || "—")}</strong>
    </div>
  `;
}

function closeBookingDetail() {
  detailOverlay.classList.add("hidden");
  currentBooking = null;
}

/* =========================
   BOOKING ACTIONS
========================= */
async function postBookingAction(url, successMessage) {
  const response = await fetchWithAuth(url, { method: "POST" });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || successMessage);
  }

  showToast(data.message || successMessage, "success");

  const bookingId = currentBooking?.booking_id;

  await loadBookings();
  await loadPayments();

  if (bookingId) {
    await openBookingDetail(bookingId);
  } else {
    closeBookingDetail();
  }
}

function handleCheckIn() {
  if (!currentBooking) return;

  openConfirmModal(
    `Bạn có chắc muốn check-in booking "${currentBooking.booking_code}" không?`,
    async () => {
      try {
        await postBookingAction(
          `${API_BASE_URL}/receptionist/bookings/${currentBooking.booking_id}/check-in`,
          "Check-in thành công."
        );
      } catch (error) {
        console.error("handleCheckIn error:", error);
        showToast(error.message || "Booking đã check-in rồi hoặc không thể check-in.", "error");
      }
    }
  );
}

function handleCheckOut() {
  if (!currentBooking) return;

  openConfirmModal(
    `Bạn có chắc muốn check-out booking "${currentBooking.booking_code}" không?`,
    async () => {
      try {
        await postBookingAction(
          `${API_BASE_URL}/receptionist/bookings/${currentBooking.booking_id}/check-out`,
          "Check-out thành công."
        );
      } catch (error) {
        console.error("handleCheckOut error:", error);
        showToast(error.message || "Booking đã check-out rồi hoặc chưa check-in.", "error");
      }
    }
  );
}

function handleCancelBooking() {
  if (!currentBooking) return;

  openConfirmModal(
    `Bạn có chắc muốn hủy booking "${currentBooking.booking_code}" không?`,
    async () => {
      try {
        await postBookingAction(
          `${API_BASE_URL}/receptionist/bookings/${currentBooking.booking_id}/cancel`,
          "Hủy booking thành công."
        );
      } catch (error) {
        console.error("handleCancelBooking error:", error);
        showToast(error.message || "Booking đã bị hủy hoặc không thể hủy.", "error");
      }
    }
  );
}
/* =========================
   RESET
========================= */
function resetBookingFilters() {
  bookingFilterForm.reset();
  hideDateFilterError();
  loadBookings();
}

function resetPaymentFilters() {
  paymentFilterForm.reset();
  applyPaymentFilters();
}

/* =========================
   EVENTS
========================= */
function bindEvents() {
  logoutBtn?.addEventListener("click", handleLogout);

  showBookingTabBtn?.addEventListener("click", showBookingTab);
  showPaymentTabBtn?.addEventListener("click", showPaymentTab);

  bookingFilterForm?.addEventListener("submit", loadBookings);
  resetBookingFilterBtn?.addEventListener("click", resetBookingFilters);

  paymentFilterForm?.addEventListener("submit", applyPaymentFilters);
  resetPaymentFilterBtn?.addEventListener("click", resetPaymentFilters);

  fromDateInput?.addEventListener("input", hideDateFilterError);
  toDateInput?.addEventListener("input", hideDateFilterError);

  bookingPrevPageBtn?.addEventListener("click", () => {
    if (bookingCurrentPage > 1) {
      bookingCurrentPage--;
      renderBookingTable();
      renderBookingPagination();
    }
  });

  bookingNextPageBtn?.addEventListener("click", () => {
    const totalPages = Math.ceil(bookingResults.length / BOOKING_PAGE_SIZE);
    if (bookingCurrentPage < totalPages) {
      bookingCurrentPage++;
      renderBookingTable();
      renderBookingPagination();
    }
  });

  paymentPrevPageBtn?.addEventListener("click", () => {
    if (paymentCurrentPage > 1) {
      paymentCurrentPage--;
      renderPaymentTable();
      renderPaymentPagination();
    }
  });

  paymentNextPageBtn?.addEventListener("click", () => {
    const totalPages = Math.ceil(filteredPayments.length / PAYMENT_PAGE_SIZE);
    if (paymentCurrentPage < totalPages) {
      paymentCurrentPage++;
      renderPaymentTable();
      renderPaymentPagination();
    }
  });

  closeDetailBtn?.addEventListener("click", closeBookingDetail);
  checkInBtn?.addEventListener("click", handleCheckIn);
  checkOutBtn?.addEventListener("click", handleCheckOut);
  cancelBookingBtn?.addEventListener("click", handleCancelBooking);

  detailOverlay?.addEventListener("click", (event) => {
    if (event.target === detailOverlay) {
      closeBookingDetail();
    }
  });

  confirmOverlay?.addEventListener("click", (event) => {
    if (event.target === confirmOverlay) {
      closeConfirmModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (detailOverlay && !detailOverlay.classList.contains("hidden")) {
        closeBookingDetail();
      }

      if (confirmOverlay && !confirmOverlay.classList.contains("hidden")) {
        closeConfirmModal();
      }
    }
  });
}

/* =========================
   INIT
========================= */
async function initReceptionistBookingPaymentPage() {
  if (!ensureReceptionistAccess()) return;

  if (receptionistNameBadge && currentUser?.full_name) {
    receptionistNameBadge.textContent = currentUser.full_name;
  }

  bindEvents();
  showBookingTab();
  await loadBookings();
  await loadPayments();
}

initReceptionistBookingPaymentPage();