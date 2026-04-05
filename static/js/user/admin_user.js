// admin_user.js
const API_BASE_URL = window.location.origin;
const accessToken = localStorage.getItem("access_token");
const currentUser = JSON.parse(localStorage.getItem("current_user") || "null");

const updateLogsList = document.getElementById("updateLogsList");
const deleteRequestsTableBody = document.getElementById("deleteRequestsBody");
const logoutBtn = document.getElementById("logoutBtn");
const adminNameBadge = document.getElementById("adminNameBadge");

const detailOverlay = document.getElementById("detailOverlay");
const closeDetailBtn = document.getElementById("closeDetailBtn");
const approveBtn = document.getElementById("approveBtn");
const rejectBtn = document.getElementById("rejectBtn");

const detailStatus = document.getElementById("detailStatus");
const detailUserInfo = document.getElementById("detailUserInfo");
const detailReason = document.getElementById("detailReason");

const filterButtons = document.querySelectorAll(".filter-btn");

let currentRequestId = null;
let currentRequestStatus = null;
let allDeleteRequests = [];
let currentFilter = "ALL";

function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${accessToken}`
  };
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("vi-VN");
}

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function ensureAdminAccess() {
  if (!accessToken || !currentUser) {
    alert("Bạn chưa đăng nhập.");
window.location.href = "/";
    return false;
  }

  if (currentUser.role_name !== "Admin") {
    alert("Bạn không có quyền vào trang admin.");
    window.location.href = "/user-info-page";
    return false;
  }

  if (adminNameBadge) {
    adminNameBadge.textContent = currentUser.full_name || "Admin";
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
    alert("Phiên đăng nhập không hợp lệ hoặc bạn không có quyền truy cập.");
    localStorage.removeItem("access_token");
    localStorage.removeItem("current_user");
window.location.href = "/";
    throw new Error("Unauthorized");
  }

  return response;
}

async function loadUpdateLogs() {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/admin/update-logs`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không tải được danh sách update logs.");
    }

    renderUpdateLogs(data);
  } catch (error) {
    console.error("loadUpdateLogs error:", error);
    if (updateLogsList) {
      updateLogsList.innerHTML = `<div class="empty-state">Không tải được dữ liệu update logs.</div>`;
    }
  }
}

function renderUpdateLogs(logs) {
  if (!updateLogsList) return;

  if (!logs || logs.length === 0) {
    updateLogsList.innerHTML = `<div class="empty-state">Chưa có log cập nhật thông tin nào.</div>`;
    return;
  }

  updateLogsList.innerHTML = logs.map((log) => `
    <div class="log-item">
      <div class="log-title">
        Người dùng <strong>${escapeHtml(log.full_name)}</strong> đã cập nhật thông tin
      </div>
      <div class="log-sub">
        User ID: ${escapeHtml(log.user_id)} · Lúc: ${escapeHtml(formatDate(log.updated_at))}
      </div>
    </div>
  `).join("");
}

async function loadDeleteRequests() {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/admin/delete-requests`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không tải được danh sách request xóa tài khoản.");
    }

    allDeleteRequests = Array.isArray(data) ? data : [];
    renderDeleteRequests();
  } catch (error) {
    console.error("loadDeleteRequests error:", error);
    if (deleteRequestsTableBody) {
      deleteRequestsTableBody.innerHTML = `
        <tr>
          <td colspan="6" class="empty-cell">Không tải được dữ liệu request xóa tài khoản.</td>
        </tr>
      `;
    }
  }
}

function renderDeleteRequests() {
  if (!deleteRequestsTableBody) return;

  const filtered = currentFilter === "ALL"
    ? allDeleteRequests
    : allDeleteRequests.filter((item) => item.status === currentFilter);

  if (filtered.length === 0) {
    deleteRequestsTableBody.innerHTML = `
      <tr>
        <td colspan="6" class="table-empty">Không có request phù hợp.</td>
      </tr>
    `;
    return;
  }

  deleteRequestsTableBody.innerHTML = filtered.map((item) => `
    <tr>
      <td>${escapeHtml(item.request_id)}</td>
      <td>${escapeHtml(item.user_id)}</td>
      <td>${escapeHtml(item.full_name)}</td>
      <td>
        <span class="status-chip status-${String(item.status).toLowerCase()}">
          ${escapeHtml(item.status)}
        </span>
      </td>
      <td>${escapeHtml(formatDate(item.created_at))}</td>
      <td>
        <button class="view-btn" data-request-id="${item.request_id}">
          Xem chi tiết
        </button>
      </td>
    </tr>
  `).join("");

  deleteRequestsTableBody.querySelectorAll(".view-btn").forEach((btn) => {
    btn.addEventListener("click", () => openDetailModal(btn.dataset.requestId));
  });
}

async function openDetailModal(requestId) {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/admin/delete-requests/${requestId}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không tải được chi tiết request.");
    }

    currentRequestId = data.request_id;
    currentRequestStatus = data.request_status;

    fillDetailModal(data);
    detailOverlay?.classList.remove("hidden");
    document.body.classList.add("modal-open");
  } catch (error) {
    console.error("openDetailModal error:", error);
    alert(error.message || "Không mở được chi tiết request.");
  }
}

function fillDetailModal(data) {
  if (detailStatus) {
    detailStatus.textContent = data.request_status || "—";
    detailStatus.className = `status-chip status-${String(data.request_status || "").toLowerCase()}`;
  }

  if (detailUserInfo) {
    detailUserInfo.innerHTML = `
      <div class="detail-item">
        <span>Request ID</span>
        <strong>${escapeHtml(data.request_id ?? "—")}</strong>
      </div>
      <div class="detail-item">
        <span>User ID</span>
        <strong>${escapeHtml(data.user_id ?? "—")}</strong>
      </div>
      <div class="detail-item">
        <span>Họ tên</span>
        <strong>${escapeHtml(data.user?.full_name || "—")}</strong>
      </div>
      <div class="detail-item">
        <span>Email</span>
        <strong>${escapeHtml(data.user?.email || "—")}</strong>
      </div>
      <div class="detail-item">
        <span>Số điện thoại</span>
        <strong>${escapeHtml(data.user?.phone || "—")}</strong>
      </div>
      <div class="detail-item">
        <span>CCCD</span>
        <strong>${escapeHtml(data.user?.citizen_id || "—")}</strong>
      </div>
      <div class="detail-item">
        <span>Địa chỉ</span>
        <strong>${escapeHtml(data.user?.address || "—")}</strong>
      </div>
      <div class="detail-item">
        <span>Role</span>
        <strong>${escapeHtml(data.user?.role_name || "—")}</strong>
      </div>
      <div class="detail-item">
        <span>Trạng thái tài khoản</span>
        <strong>${escapeHtml(data.user?.status || "—")}</strong>
      </div>
    `;
  }

  if (detailReason) {
    detailReason.textContent = data.reason || "Không có lí do";
  }

  const isPending = data.request_status === "Pending";
  if (approveBtn) approveBtn.disabled = !isPending;
  if (rejectBtn) rejectBtn.disabled = !isPending;
}

function closeDetailModal() {
  detailOverlay?.classList.add("hidden");
  document.body.classList.remove("modal-open");
  currentRequestId = null;
  currentRequestStatus = null;
}

async function approveCurrentRequest() {
  if (!currentRequestId) return;
  if (currentRequestStatus !== "Pending") {
    alert("Chỉ request Pending mới được approve.");
    return;
  }

  const confirmed = confirm("Bạn có chắc muốn approve request xóa tài khoản này không?");
  if (!confirmed) return;

  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/admin/delete-request/${currentRequestId}/approve`,
      { method: "PUT" }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Approve thất bại.");
    }

    alert(data.message || "Approve thành công.");
    closeDetailModal();
    await loadDeleteRequests();
  } catch (error) {
    console.error("approveCurrentRequest error:", error);
    alert(error.message || "Approve thất bại.");
  }
}

async function rejectCurrentRequest() {
  if (!currentRequestId) return;
  if (currentRequestStatus !== "Pending") {
    alert("Chỉ request Pending mới được reject.");
    return;
  }

  const confirmed = confirm("Bạn có chắc muốn reject request này không?");
  if (!confirmed) return;

  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/admin/delete-request/${currentRequestId}/reject`,
      { method: "PUT" }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Reject thất bại.");
    }

    alert(data.message || "Reject thành công.");
    closeDetailModal();
    await loadDeleteRequests();
  } catch (error) {
    console.error("rejectCurrentRequest error:", error);
    alert(error.message || "Reject thất bại.");
  }
}

function handleLogout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("current_user");
window.location.href = "/";
}

function bindEvents() {
  filterButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      filterButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.dataset.status;
      renderDeleteRequests();
    });
  });

  closeDetailBtn?.addEventListener("click", closeDetailModal);
  approveBtn?.addEventListener("click", approveCurrentRequest);
  rejectBtn?.addEventListener("click", rejectCurrentRequest);
  logoutBtn?.addEventListener("click", handleLogout);

  detailOverlay?.addEventListener("click", (event) => {
    if (event.target === detailOverlay) {
      closeDetailModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && detailOverlay && !detailOverlay.classList.contains("hidden")) {
      closeDetailModal();
    }
  });
}

async function initAdminPage() {
  if (!ensureAdminAccess()) return;
  bindEvents();
  await Promise.all([
    loadUpdateLogs(),
    loadDeleteRequests()
  ]);
}

initAdminPage();
