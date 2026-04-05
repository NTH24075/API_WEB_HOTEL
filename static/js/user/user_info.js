const API_BASE_URL = window.location.origin;
const accessToken = localStorage.getItem("access_token");
const currentUser = JSON.parse(localStorage.getItem("current_user") || "null");

const logoutBtn = document.getElementById("logoutBtn");

const userFullName = document.getElementById("userFullName");
const userEmail = document.getElementById("userEmail");
const userPhone = document.getElementById("userPhone");
const userCitizenId = document.getElementById("userCitizenId");
const userAddress = document.getElementById("userAddress");
const userAvatar = document.getElementById("userAvatar");
const userRole = document.getElementById("userRole");
const userStatus = document.getElementById("userStatus");
const userNotice = document.getElementById("userNotice");

const openUpdateBtn = document.getElementById("openUpdateBtn");
const openDeleteRequestBtn = document.getElementById("openDeleteRequestBtn");

const updateOverlay = document.getElementById("updateOverlay");
const closeUpdateBtn = document.getElementById("closeUpdateBtn");
const updateForm = document.getElementById("updateForm");

const deleteOverlay = document.getElementById("deleteOverlay");
const closeDeleteBtn = document.getElementById("closeDeleteBtn");
const deleteRequestForm = document.getElementById("deleteRequestForm");

function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${accessToken}`
  };
}

function ensureUserAccess() {
  if (!accessToken || !currentUser) {
    alert("Bạn chưa đăng nhập.");
window.location.href = "/";
    return false;
  }

  if (currentUser.role_name === "Admin") {
    window.location.href = "/admin-user-page";
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
    alert("Phiên đăng nhập không hợp lệ.");
    localStorage.removeItem("access_token");
    localStorage.removeItem("current_user");
window.location.href = "/";
    throw new Error("Unauthorized");
  }

  return response;
}

function setText(el, value) {
  if (!el) return;
  el.textContent = value || "—";
}

function getNullAvatar() {
  return "data:image/svg+xml;utf8," + encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
      <rect width="120" height="120" rx="60" fill="#E5E7EB"/>
      <circle cx="60" cy="45" r="22" fill="#9CA3AF"/>
      <path d="M25 98c7-18 25-28 35-28s28 10 35 28" fill="#9CA3AF"/>
    </svg>
  `);
}

function getAvatarSrc(url) {
  return url && String(url).trim() ? url : getNullAvatar();
}

function setAvatar(url, fallbackName) {
  if (!userAvatar) return;
  userAvatar.src = getAvatarSrc(url);
  userAvatar.alt = fallbackName || "Avatar";
}

function renderNotice(user) {
  if (!userNotice) return;

  const missingFields = [];
  if (!user.phone) missingFields.push("số điện thoại");
  if (!user.citizen_id) missingFields.push("CCCD");
  if (!user.address) missingFields.push("địa chỉ");

  if (missingFields.length === 0) {
    userNotice.innerHTML = "";
    userNotice.classList.add("hidden");
    return;
  }

  userNotice.innerHTML = `Bạn nên bổ sung: <strong>${missingFields.join(", ")}</strong>.`;
  userNotice.classList.remove("hidden");
}

function fillUserInfo(user) {
  setText(userFullName, user.full_name);
  setText(userEmail, user.email);
  setText(userPhone, user.phone);
  setText(userCitizenId, user.citizen_id);
  setText(userAddress, user.address);
  setText(userRole, user.role_name);
  setText(userStatus, user.status);
  setAvatar(user.avatar_url, user.full_name);
  renderNotice(user);
}

function fillUpdateForm(user) {
  const fullNameInput = document.getElementById("updateFullName");
  const phoneInput = document.getElementById("updatePhone");
  const citizenIdInput = document.getElementById("updateCitizenId");
  const addressInput = document.getElementById("updateAddress");
  const avatarUrlInput = document.getElementById("updateAvatarUrl");

  if (fullNameInput) fullNameInput.value = user.full_name || "";
  if (phoneInput) phoneInput.value = user.phone || "";
  if (citizenIdInput) citizenIdInput.value = user.citizen_id || "";
  if (addressInput) addressInput.value = user.address || "";
  if (avatarUrlInput) avatarUrlInput.value = user.avatar_url || "";
}

async function loadMyInfo() {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/auth/me`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không tải được thông tin tài khoản.");
    }

    localStorage.setItem("current_user", JSON.stringify(data));
    fillUserInfo(data);
    fillUpdateForm(data);
  } catch (error) {
    console.error("loadMyInfo error:", error);
    alert(error.message || "Không tải được thông tin tài khoản.");
  }
}

function openModal(overlay) {
  if (!overlay) return;
  overlay.classList.remove("hidden");
  overlay.classList.add("show");
  document.body.classList.add("modal-open");
}

function closeModal(overlay) {
  if (!overlay) return;
  overlay.classList.remove("show");
  overlay.classList.add("hidden");

  const hasOpenedModal =
    updateOverlay?.classList.contains("show") ||
    deleteOverlay?.classList.contains("show");

  if (!hasOpenedModal) {
    document.body.classList.remove("modal-open");
  }
}

async function handleUpdateSubmit(event) {
  event.preventDefault();

  const payload = {
    full_name: document.getElementById("updateFullName")?.value.trim(),
    phone: document.getElementById("updatePhone")?.value.trim() || null,
    citizen_id: document.getElementById("updateCitizenId")?.value.trim() || null,
    address: document.getElementById("updateAddress")?.value.trim() || null,
    avatar_url: document.getElementById("updateAvatarUrl")?.value.trim() || null
  };

  if (!payload.full_name) {
    alert("Họ tên không được để trống.");
    return;
  }

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/user/me`, {
      method: "PUT",
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Cập nhật thất bại.");
    }

    if (data.user) {
      localStorage.setItem("current_user", JSON.stringify(data.user));
      fillUserInfo(data.user);
      fillUpdateForm(data.user);
    }

    alert(data.message || "Cập nhật thông tin thành công.");
    closeModal(updateOverlay);
  } catch (error) {
    console.error("handleUpdateSubmit error:", error);
    alert(error.message || "Cập nhật thất bại.");
  }
}

async function handleDeleteRequestSubmit(event) {
  event.preventDefault();

  const reason = document.getElementById("deleteReason")?.value.trim() || null;

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/user/delete-request`, {
      method: "POST",
      body: JSON.stringify({ reason })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Gửi request xóa tài khoản thất bại.");
    }

    alert(data.message || "Đã gửi request xóa tài khoản.");
    deleteRequestForm?.reset();
    closeModal(deleteOverlay);
  } catch (error) {
    console.error("handleDeleteRequestSubmit error:", error);
    alert(error.message || "Gửi request thất bại.");
  }
}

function handleLogout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("current_user");
window.location.href = "/";
}

function bindEvents() {
  logoutBtn?.addEventListener("click", handleLogout);

  openUpdateBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    openModal(updateOverlay);
  });

  closeUpdateBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    closeModal(updateOverlay);
  });

  updateForm?.addEventListener("submit", handleUpdateSubmit);

  openDeleteRequestBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    openModal(deleteOverlay);
  });

  closeDeleteBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    closeModal(deleteOverlay);
  });

  deleteRequestForm?.addEventListener("submit", handleDeleteRequestSubmit);

  updateOverlay?.addEventListener("click", (event) => {
    if (event.target === updateOverlay) {
      closeModal(updateOverlay);
    }
  });

  deleteOverlay?.addEventListener("click", (event) => {
    if (event.target === deleteOverlay) {
      closeModal(deleteOverlay);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeModal(updateOverlay);
      closeModal(deleteOverlay);
    }
  });
}

async function initUserPage() {
  if (!ensureUserAccess()) return;

  closeModal(updateOverlay);
  closeModal(deleteOverlay);

  bindEvents();
  await loadMyInfo();
}

initUserPage();
