/* =========================================
   CẤU HÌNH CHUNG + LẤY TOKEN / USER
========================================= */
const API_BASE_URL = window.location.origin;
const accessToken = localStorage.getItem("access_token");
const currentUser = JSON.parse(localStorage.getItem("current_user") || "null");

/* =========================================
   DOM: TOPBAR
========================================= */
const logoutBtn = document.getElementById("logoutBtn");
const receptionistNameBadge = document.getElementById("receptionistNameBadge");

/* =========================================
   DOM: FORM GÁN SERVICE
========================================= */
const assignServiceForm = document.getElementById("assignServiceForm");
const serviceSelect = document.getElementById("serviceSelect");
const servicePreviewBox = document.getElementById("servicePreviewBox");
const customPriceInput = document.getElementById("customPriceInput");
const isAvailableInput = document.getElementById("isAvailableInput");

/* =========================================
   DOM: HOTEL INFO
========================================= */
const hotelNameText = document.getElementById("hotelNameText");
const hotelAddressText = document.getElementById("hotelAddressText");

/* =========================================
   DOM: FILTER + TABLE
========================================= */
const filterForm = document.getElementById("filterForm");
const resetFilterBtn = document.getElementById("resetFilterBtn");
const searchKeyword = document.getElementById("searchKeyword");
const availabilityFilter = document.getElementById("availabilityFilter");
const minPriceFilter = document.getElementById("minPriceFilter");
const maxPriceFilter = document.getElementById("maxPriceFilter");
const priceFilterError = document.getElementById("priceFilterError");
const hotelServiceTableBody = document.getElementById("hotelServiceTableBody");
const resultCount = document.getElementById("resultCount");

/* =========================================
   DOM: PAGINATION
========================================= */
const paginationWrap = document.getElementById("paginationWrap");
const paginationNumbers = document.getElementById("paginationNumbers");
const prevPageBtn = document.getElementById("prevPageBtn");
const nextPageBtn = document.getElementById("nextPageBtn");

/* =========================================
   DOM: CATALOG
========================================= */
const serviceCatalogGrid = document.getElementById("serviceCatalogGrid");

/* =========================================
   DOM: MODAL DETAIL / UPDATE
========================================= */
const detailOverlay = document.getElementById("detailOverlay");
const closeDetailBtn = document.getElementById("closeDetailBtn");
const detailAvailabilityBadge = document.getElementById("detailAvailabilityBadge");
const detailHotelServiceInfo = document.getElementById("detailHotelServiceInfo");
const detailDescription = document.getElementById("detailDescription");

const updateHotelServiceForm = document.getElementById("updateHotelServiceForm");
const updateCustomPriceInput = document.getElementById("updateCustomPriceInput");
const updateIsAvailableInput = document.getElementById("updateIsAvailableInput");
const deleteHotelServiceBtn = document.getElementById("deleteHotelServiceBtn");

/* =========================================
   DOM: CONFIRM + TOAST
========================================= */
const confirmOverlay = document.getElementById("confirmOverlay");
const confirmMessage = document.getElementById("confirmMessage");
const confirmCancelBtn = document.getElementById("confirmCancelBtn");
const confirmOkBtn = document.getElementById("confirmOkBtn");
const toast = document.getElementById("toast");

/* =========================================
   STATE CHUNG
========================================= */
let systemServices = [];
let hotelServices = [];
let filteredHotelServices = [];
let currentHotelService = null;
let currentHotelInfo = null;
let currentPage = 1;
const PAGE_SIZE = 5;

/* =========================================
   HEADER AUTH CHO API
========================================= */
function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${accessToken}`
  };
}

/* =========================================
   CHECK QUYỀN RECEPTIONIST
========================================= */
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

/* =========================================
   FETCH CÓ KÈM TOKEN
========================================= */
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

/* =========================================
   HÀM HỖ TRỢ CHUNG
========================================= */
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

function parseNumberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const num = Number(value);
  return Number.isNaN(num) ? null : num;
}

function formatUnit(value) {
  return value || "Đang cập nhật";
}

function getAvailabilityLabel(isAvailable) {
  return isAvailable ? "Đang khả dụng" : "Tạm ngưng";
}

function getAvailabilityChipClass(isAvailable) {
  return isAvailable ? "status-chip available" : "status-chip unavailable";
}

/* =========================================
   TOAST
========================================= */
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

/* =========================================
   CONFIRM MODAL
========================================= */
function openConfirmModal(message, onConfirm) {
  if (!confirmOverlay || !confirmMessage || !confirmOkBtn || !confirmCancelBtn) {
    const accepted = confirm(message);
    if (accepted) onConfirm();
    return;
  }

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
  if (!confirmOverlay) return;

  confirmOverlay.classList.add("hidden");
  confirmOkBtn.onclick = null;
  confirmCancelBtn.onclick = null;
}

/* =========================================
   PRICE FILTER ERROR
========================================= */
function showPriceFilterError(message) {
  if (priceFilterError) {
    priceFilterError.textContent = message;
    priceFilterError.classList.remove("hidden");
  }

  minPriceFilter?.classList.add("input-error");
  maxPriceFilter?.classList.add("input-error");
}

function hidePriceFilterError() {
  if (priceFilterError) {
    priceFilterError.classList.add("hidden");
  }

  minPriceFilter?.classList.remove("input-error");
  maxPriceFilter?.classList.remove("input-error");
}

/* =========================================
   LOGOUT
========================================= */
function handleLogout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("current_user");
  window.location.href = "/auth-page";
}

/* =========================================
   RENDER HOTEL INFO
========================================= */
function renderHotelInfo() {
  if (hotelNameText) {
    hotelNameText.textContent = currentHotelInfo?.hotel_name || "Đang cập nhật";
  }

  if (hotelAddressText) {
    hotelAddressText.textContent = currentHotelInfo?.address || "Đang cập nhật";
  }
}

/* =========================================
   LOAD ALL ACTIVE SERVICES
========================================= */
async function loadSystemServices() {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/receptionist/services`, {
      method: "GET"
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không tải được danh sách service hệ thống.");
    }

    systemServices = Array.isArray(data) ? data : [];
    renderServiceSelect();
    renderServiceCatalog();
  } catch (error) {
    console.error("loadSystemServices error:", error);
    servicePreviewBox.textContent = error.message || "Không tải được danh sách service.";
    serviceCatalogGrid.innerHTML = `<div class="empty-state">Không tải được danh sách dịch vụ hệ thống.</div>`;
    showToast(error.message || "Không tải được danh sách dịch vụ.", "error");
  }
}

/* =========================================
   LOAD HOTEL SERVICES
========================================= */
async function loadHotelServices() {
  hotelServiceTableBody.innerHTML = `
    <tr>
      <td colspan="7" class="table-empty">Đang tải dữ liệu...</td>
    </tr>
  `;

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/receptionist/hotel-services`, {
      method: "GET"
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không tải được dịch vụ của khách sạn.");
    }

    currentHotelInfo = data?.hotel || null;
    hotelServices = Array.isArray(data?.items) ? data.items : [];

    renderHotelInfo();
    applyHotelServiceFilters();
  } catch (error) {
    console.error("loadHotelServices error:", error);

    hotelServiceTableBody.innerHTML = `
      <tr>
        <td colspan="7" class="table-empty">Không tải được dữ liệu.</td>
      </tr>
    `;

    resultCount.textContent = "0 kết quả";
    paginationWrap?.classList.add("hidden");

    if (hotelNameText) hotelNameText.textContent = "Không tải được";
    if (hotelAddressText) hotelAddressText.textContent = "Không tải được";

    showToast(error.message || "Không tải được dịch vụ khách sạn.", "error");
  }
}

/* =========================================
   RENDER SELECT SERVICE
========================================= */
function renderServiceSelect() {
  if (!serviceSelect) return;

  const options = systemServices.map(item => `
    <option value="${item.service_id}">
      ${escapeHtml(item.service_name)} - ${escapeHtml(formatMoney(item.price))}
    </option>
  `).join("");

  serviceSelect.innerHTML = `
    <option value="">-- Chọn dịch vụ --</option>
    ${options}
  `;
}

/* =========================================
   RENDER CATALOG SERVICE
========================================= */
function renderServiceCatalog() {
  if (!serviceCatalogGrid) return;

  if (!systemServices.length) {
    serviceCatalogGrid.innerHTML = `<div class="empty-state">Không có dịch vụ nào đang hoạt động.</div>`;
    return;
  }

  serviceCatalogGrid.innerHTML = systemServices.map(service => `
    <article class="catalog-card">
      <h3>${escapeHtml(service.service_name || "—")}</h3>
      <p class="catalog-description">${escapeHtml(service.description || "Chưa có mô tả.")}</p>

      <div class="catalog-meta">
        <div><strong>Giá mặc định:</strong> ${escapeHtml(formatMoney(service.price))}</div>
        <div><strong>Đơn vị:</strong> ${escapeHtml(formatUnit(service.unit))}</div>
      </div>

      <div class="catalog-footer">
        <span class="status-chip">Đang hoạt động</span>
        <button
          type="button"
          class="catalog-btn"
          data-service-id="${service.service_id}">
          Chọn nhanh
        </button>
      </div>
    </article>
  `).join("");

  serviceCatalogGrid.querySelectorAll(".catalog-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      serviceSelect.value = btn.dataset.serviceId;
      updateServicePreview();
      serviceSelect.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });
}

/* =========================================
   SERVICE PREVIEW
========================================= */
function updateServicePreview() {
  const selectedId = Number(serviceSelect.value);
  const service = systemServices.find(item => Number(item.service_id) === selectedId);

  if (!service) {
    servicePreviewBox.textContent = "Chọn một dịch vụ để xem mô tả và giá mặc định.";
    return;
  }

  servicePreviewBox.textContent =
    `Tên dịch vụ: ${service.service_name || "—"}\n` +
    `Giá mặc định: ${formatMoney(service.price)}\n` +
    `Đơn vị: ${service.unit || "Đang cập nhật"}\n` +
    `Mô tả: ${service.description || "Chưa có mô tả"}`;
}

/* =========================================
   GÁN SERVICE VÀO HOTEL
========================================= */
async function assignServiceToHotel(event) {
  event.preventDefault();

  const serviceId = Number(serviceSelect.value);
  const customPrice = parseNumberOrNull(customPriceInput.value);
  const isAvailable = !!isAvailableInput.checked;

  if (!serviceId) {
    showToast("Vui lòng chọn dịch vụ.", "error");
    return;
  }

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/receptionist/hotel-services`, {
      method: "POST",
      body: JSON.stringify({
        service_id: serviceId,
        custom_price: customPrice,
        is_available: isAvailable
      })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Gán dịch vụ thất bại.");
    }

    assignServiceForm.reset();
    isAvailableInput.checked = true;
    updateServicePreview();

    showToast(data.message || "Gán dịch vụ thành công.", "success");
    await loadHotelServices();
  } catch (error) {
    console.error("assignServiceToHotel error:", error);
    showToast(error.message || "Gán dịch vụ thất bại.", "error");
  }
}

/* =========================================
   FILTER HOTEL SERVICES
========================================= */
function applyHotelServiceFilters(event) {
  if (event) event.preventDefault();

  const keyword = (searchKeyword?.value || "").trim().toLowerCase();
  const availability = availabilityFilter?.value || "all";
  const minPrice = parseNumberOrNull(minPriceFilter?.value);
  const maxPrice = parseNumberOrNull(maxPriceFilter?.value);

  hidePriceFilterError();

  if (minPrice !== null && maxPrice !== null && minPrice > maxPrice) {
    showPriceFilterError("Giá tối thiểu không được lớn hơn giá tối đa.");
    filteredHotelServices = [];
    hotelServiceTableBody.innerHTML = `
      <tr>
        <td colspan="7" class="table-empty">Vui lòng kiểm tra lại bộ lọc giá.</td>
      </tr>
    `;
    resultCount.textContent = "0 kết quả";
    paginationWrap?.classList.add("hidden");
    return;
  }

  filteredHotelServices = hotelServices.filter(item => {
    const matchKeyword =
      !keyword ||
      String(item.service_name || "").toLowerCase().includes(keyword);

    const matchAvailability =
      availability === "all" ||
      (availability === "available" && item.is_available === true) ||
      (availability === "unavailable" && item.is_available === false);

    const finalPrice = Number(item.final_price || 0);

    const matchMinPrice = minPrice === null || finalPrice >= minPrice;
    const matchMaxPrice = maxPrice === null || finalPrice <= maxPrice;

    return matchKeyword && matchAvailability && matchMinPrice && matchMaxPrice;
  });

  currentPage = 1;
  renderHotelServiceTable();
  renderPagination();
}

/* =========================================
   RESET FILTER
========================================= */
function resetFilterForm() {
  filterForm?.reset();
  hidePriceFilterError();
  applyHotelServiceFilters();
}

/* =========================================
   PHÂN TRANG
========================================= */
function getPaginatedHotelServices() {
  const start = (currentPage - 1) * PAGE_SIZE;
  const end = start + PAGE_SIZE;
  return filteredHotelServices.slice(start, end);
}

function renderPagination() {
  if (!paginationWrap || !paginationNumbers || !prevPageBtn || !nextPageBtn) return;

  const totalPages = Math.ceil(filteredHotelServices.length / PAGE_SIZE);

  if (totalPages <= 1) {
    paginationWrap.classList.add("hidden");
    return;
  }

  paginationWrap.classList.remove("hidden");
  paginationNumbers.innerHTML = "";

  for (let i = 1; i <= totalPages; i++) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `page-btn ${i === currentPage ? "active" : ""}`;
    btn.textContent = i;

    btn.addEventListener("click", () => {
      currentPage = i;
      renderHotelServiceTable();
      renderPagination();
    });

    paginationNumbers.appendChild(btn);
  }

  prevPageBtn.disabled = currentPage === 1;
  nextPageBtn.disabled = currentPage === totalPages;
}

/* =========================================
   RENDER TABLE HOTEL SERVICE
========================================= */
function renderHotelServiceTable() {
  resultCount.textContent = `${filteredHotelServices.length} kết quả`;

  const currentItems = getPaginatedHotelServices();

  if (!currentItems.length) {
    hotelServiceTableBody.innerHTML = `
      <tr>
        <td colspan="7" class="table-empty">Không có dịch vụ phù hợp.</td>
      </tr>
    `;
    return;
  }

  hotelServiceTableBody.innerHTML = currentItems.map(item => `
    <tr>
      <td>${escapeHtml(item.hotel_service_id)}</td>
      <td>${escapeHtml(item.service_name || "—")}</td>
      <td>${escapeHtml(formatMoney(item.default_price))}</td>
      <td>${escapeHtml(formatMoney(item.final_price))}</td>
      <td>${escapeHtml(formatUnit(item.unit))}</td>
      <td>
        <span class="${getAvailabilityChipClass(item.is_available)}">
          ${escapeHtml(getAvailabilityLabel(item.is_available))}
        </span>
      </td>
      <td>
        <button class="view-btn" data-hotel-service-id="${item.hotel_service_id}" type="button">
          Cập nhật
        </button>
      </td>
    </tr>
  `).join("");

  hotelServiceTableBody.querySelectorAll(".view-btn").forEach(btn => {
    btn.addEventListener("click", () => openDetailModal(Number(btn.dataset.hotelServiceId)));
  });
}

/* =========================================
   MODAL CHI TIẾT
========================================= */
function openDetailModal(hotelServiceId) {
  const item = hotelServices.find(service => Number(service.hotel_service_id) === Number(hotelServiceId));

  if (!item) {
    showToast("Không tìm thấy dịch vụ cần cập nhật.", "error");
    return;
  }

  currentHotelService = item;
  fillDetailModal(item);
  detailOverlay?.classList.remove("hidden");
}

function fillDetailModal(item) {
  if (!detailHotelServiceInfo || !detailAvailabilityBadge || !detailDescription) return;

  detailAvailabilityBadge.textContent = getAvailabilityLabel(item.is_available);
  detailAvailabilityBadge.className = getAvailabilityChipClass(item.is_available);

  detailHotelServiceInfo.innerHTML = `
    <div class="detail-item">
      <span>HotelService ID</span>
      <strong>${escapeHtml(item.hotel_service_id ?? "—")}</strong>
    </div>

    <div class="detail-item">
      <span>Hotel ID</span>
      <strong>${escapeHtml(item.hotel_id ?? "—")}</strong>
    </div>

    <div class="detail-item">
      <span>Service ID</span>
      <strong>${escapeHtml(item.service_id ?? "—")}</strong>
    </div>

    <div class="detail-item">
      <span>Tên dịch vụ</span>
      <strong>${escapeHtml(item.service_name || "Đang cập nhật")}</strong>
    </div>

    <div class="detail-item">
      <span>Giá mặc định</span>
      <strong>${escapeHtml(formatMoney(item.default_price))}</strong>
    </div>

    <div class="detail-item">
      <span>Giá riêng hiện tại</span>
      <strong>${escapeHtml(formatMoney(item.custom_price))}</strong>
    </div>

    <div class="detail-item">
      <span>Giá áp dụng thực tế</span>
      <strong>${escapeHtml(formatMoney(item.final_price))}</strong>
    </div>

    <div class="detail-item">
      <span>Đơn vị</span>
      <strong>${escapeHtml(formatUnit(item.unit))}</strong>
    </div>
  `;

  detailDescription.textContent = item.description || "Chưa có mô tả.";
  updateCustomPriceInput.value = item.custom_price ?? "";
  updateIsAvailableInput.checked = !!item.is_available;
}

function closeDetailModal() {
  detailOverlay?.classList.add("hidden");
  currentHotelService = null;
}

/* =========================================
   UPDATE HOTEL SERVICE
========================================= */
async function updateCurrentHotelService(event) {
  event.preventDefault();

  if (!currentHotelService || !currentHotelService.hotel_service_id) return;

  const customPriceValue = updateCustomPriceInput.value;
  const payload = {
    custom_price: customPriceValue === "" ? null : Number(customPriceValue),
    is_available: !!updateIsAvailableInput.checked
  };

  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/receptionist/hotel-services/${currentHotelService.hotel_service_id}`,
      {
        method: "PUT",
        body: JSON.stringify(payload)
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Cập nhật dịch vụ thất bại.");
    }

    closeDetailModal();
    showToast(data.message || "Cập nhật thành công.", "success");
    await loadHotelServices();
  } catch (error) {
    console.error("updateCurrentHotelService error:", error);
    showToast(error.message || "Cập nhật dịch vụ thất bại.", "error");
  }
}

/* =========================================
   DELETE HOTEL SERVICE
========================================= */
async function deleteCurrentHotelService() {
  if (!currentHotelService || !currentHotelService.hotel_service_id) return;

  openConfirmModal(
    `Bạn có chắc muốn xóa dịch vụ "${currentHotelService.service_name}" khỏi khách sạn không?`,
    async () => {
      try {
        const response = await fetchWithAuth(
          `${API_BASE_URL}/receptionist/hotel-services/${currentHotelService.hotel_service_id}`,
          {
            method: "DELETE"
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || "Xóa dịch vụ thất bại.");
        }

        closeDetailModal();
        showToast(data.message || "Xóa dịch vụ thành công.", "success");
        await loadHotelServices();
      } catch (error) {
        console.error("deleteCurrentHotelService error:", error);
        showToast(error.message || "Xóa dịch vụ thất bại.", "error");
      }
    }
  );
}

/* =========================================
   GẮN SỰ KIỆN
========================================= */
function bindEvents() {
  logoutBtn?.addEventListener("click", handleLogout);

  assignServiceForm?.addEventListener("submit", assignServiceToHotel);
  serviceSelect?.addEventListener("change", updateServicePreview);

  filterForm?.addEventListener("submit", applyHotelServiceFilters);
  resetFilterBtn?.addEventListener("click", resetFilterForm);

  minPriceFilter?.addEventListener("input", hidePriceFilterError);
  maxPriceFilter?.addEventListener("input", hidePriceFilterError);

  closeDetailBtn?.addEventListener("click", closeDetailModal);
  updateHotelServiceForm?.addEventListener("submit", updateCurrentHotelService);
  deleteHotelServiceBtn?.addEventListener("click", deleteCurrentHotelService);

  prevPageBtn?.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      renderHotelServiceTable();
      renderPagination();
    }
  });

  nextPageBtn?.addEventListener("click", () => {
    const totalPages = Math.ceil(filteredHotelServices.length / PAGE_SIZE);
    if (currentPage < totalPages) {
      currentPage++;
      renderHotelServiceTable();
      renderPagination();
    }
  });

  detailOverlay?.addEventListener("click", (event) => {
    if (event.target === detailOverlay) {
      closeDetailModal();
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
        closeDetailModal();
      }

      if (confirmOverlay && !confirmOverlay.classList.contains("hidden")) {
        closeConfirmModal();
      }
    }
  });
}

/* =========================================
   INIT TRANG
========================================= */
async function initReceptionistHotelServicePage() {
  if (!ensureReceptionistAccess()) return;

  if (receptionistNameBadge && currentUser?.full_name) {
    receptionistNameBadge.textContent = currentUser.full_name;
  }

  bindEvents();
  await loadSystemServices();
  await loadHotelServices();
}

initReceptionistHotelServicePage();