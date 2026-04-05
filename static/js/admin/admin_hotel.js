/* =========================================
   CẤU HÌNH CHUNG + LẤY TOKEN / USER
========================================= */
const API_BASE_URL = window.location.origin;
const accessToken = localStorage.getItem("access_token");
const currentUser = JSON.parse(localStorage.getItem("current_user") || "null");

/* =========================================
   DOM: TOPBAR / IMPORT / SEARCH
========================================= */
const logoutBtn = document.getElementById("logoutBtn");

const importHotelForm = document.getElementById("importHotelForm");
const importCityInput = document.getElementById("importCity");
const importMaxResultsInput = document.getElementById("importMaxResults");
const importResultBox = document.getElementById("importResultBox");

const searchHotelForm = document.getElementById("searchHotelForm");
const resetSearchBtn = document.getElementById("resetSearchBtn");
const hotelTableBody = document.getElementById("hotelTableBody");
const resultCount = document.getElementById("resultCount");

const searchCityInput = document.getElementById("searchCity");
const searchHotelNameInput = document.getElementById("searchHotelName");
const searchMinPriceInput = document.getElementById("searchMinPrice");
const searchMaxPriceInput = document.getElementById("searchMaxPrice");
const searchMinRatingInput = document.getElementById("searchMinRating");
const searchMaxRatingInput = document.getElementById("searchMaxRating");
const searchMinCapacityInput = document.getElementById("searchMinCapacity");
const searchMinAvailableQuantityInput = document.getElementById("searchMinAvailableQuantity");
const searchSourceInput = document.getElementById("searchSource");
const searchSortByInput = document.getElementById("searchSortBy");

/* =========================================
   DOM: MODAL CHI TIẾT
========================================= */
const detailOverlay = document.getElementById("detailOverlay");
const closeDetailBtn = document.getElementById("closeDetailBtn");
const detailSource = document.getElementById("detailSource");
const detailHotelInfo = document.getElementById("detailHotelInfo");
const detailAddress = document.getElementById("detailAddress");
const deleteHotelBtn = document.getElementById("deleteHotelBtn");

/* =========================================
   DOM: PHÂN TRANG
========================================= */
const paginationWrap = document.getElementById("paginationWrap");
const paginationNumbers = document.getElementById("paginationNumbers");
const prevPageBtn = document.getElementById("prevPageBtn");
const nextPageBtn = document.getElementById("nextPageBtn");

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
let hotelResults = [];
let currentHotel = null;
let currentPage = 1;
const PAGE_SIZE = 10;

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
   CHECK QUYỀN ADMIN
========================================= */
function ensureAdminAccess() {
  if (!accessToken || !currentUser) {
window.location.href = "/";
    return false;
  }

  if (currentUser.role_name !== "Admin") {
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
window.location.href = "/";
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

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("vi-VN");
}

function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "—";
  return Number(value).toLocaleString("vi-VN") + " VND";
}

function parseNumberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const num = Number(value);
  return Number.isNaN(num) ? null : num;
}

/* =========================================
   CHUẨN HÓA TÊN THÀNH PHỐ
   Để city đẹp hơn khi render
========================================= */
function normalizeCityName(city) {
  if (!city) return "Đang cập nhật";

  const normalized = String(city).trim().toLowerCase();

  const cityMap = {
    "hanoi": "Hà Nội",
    "ha noi": "Hà Nội",
    "ho chi minh city": "Hồ Chí Minh",
    "hochiminh": "Hồ Chí Minh",
    "ho chi minh": "Hồ Chí Minh",
    "danang": "Đà Nẵng",
    "da nang": "Đà Nẵng",
    "haiphong": "Hải Phòng",
    "hai phong": "Hải Phòng",
    "cantho": "Cần Thơ",
    "can tho": "Cần Thơ"
  };

  return cityMap[normalized] || city;
}

/* =========================================
   CHUẨN HÓA SOURCE HIỂN THỊ
========================================= */
function prettySource(value) {
  if (!value) return "Đang cập nhật";

  const raw = String(value).trim().toLowerCase();

  if (raw === "geoapify") return "Geoapify";

  return value;
}

/* =========================================
   TOAST THÔNG BÁO
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
   MODAL XÁC NHẬN XÓA
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
   LẤY PAYLOAD SEARCH TỪ FORM
========================================= */
function getSearchPayload() {
  return {
    city: searchCityInput?.value.trim() || null,
    hotel_name: searchHotelNameInput?.value.trim() || null,
    min_price: parseNumberOrNull(searchMinPriceInput?.value),
    max_price: parseNumberOrNull(searchMaxPriceInput?.value),
    min_rating: parseNumberOrNull(searchMinRatingInput?.value),
    max_rating: parseNumberOrNull(searchMaxRatingInput?.value),
    min_capacity: parseNumberOrNull(searchMinCapacityInput?.value),
    min_available_quantity: parseNumberOrNull(searchMinAvailableQuantityInput?.value),
    source: searchSourceInput?.value.trim() || null,
    sort_by: searchSortByInput?.value || "price_asc"
  };
}

/* =========================================
   IMPORT HOTEL
========================================= */
async function importHotels(event) {
  event.preventDefault();

  const city = importCityInput.value.trim();
  const maxResults = Number(importMaxResultsInput.value);

  if (!city) {
    showToast("Vui lòng nhập tên thành phố.", "error");
    return;
  }

  if (!maxResults || maxResults < 1 || maxResults > 30) {
    showToast("Số lượng tối đa phải từ 1 đến 30.", "error");
    return;
  }

  importResultBox.textContent = "Đang import khách sạn...";

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/admin/hotels/import`, {
      method: "POST",
      body: JSON.stringify({
        city: city,
        max_results: maxResults
      })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Import khách sạn thất bại.");
    }

    importResultBox.textContent =
      `Thành phố: ${normalizeCityName(data.city || "—")}\n` +
      `Tổng số khách sạn lấy được: ${data.total_from_geoapify ?? 0}\n` +
      `Số khách sạn thêm mới: ${data.inserted ?? 0}\n` +
      `Số khách sạn bị bỏ qua: ${data.skipped ?? 0}\n` +
      `ID khách sạn đã thêm: ${(data.inserted_hotel_ids || []).join(", ") || "Không có"}\n` +
      `Trạng thái: ${data.message || "Import thành công"}`;

    showToast("Import khách sạn thành công.", "success");

    /* Sau khi import xong thì load lại danh sách */
    await searchHotels();
  } catch (error) {
    console.error("importHotels error:", error);
    importResultBox.textContent = error.message || "Import thất bại.";
    showToast(error.message || "Import thất bại.", "error");
  }
}

/* =========================================
   SEARCH HOTEL
========================================= */
async function searchHotels(event) {
  if (event) event.preventDefault();

  const payload = getSearchPayload();

  hotelTableBody.innerHTML = `
    <tr>
      <td colspan="7" class="table-empty">Đang tải dữ liệu...</td>
    </tr>
  `;

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/admin/hotels/search`, {
      method: "POST",
      body: JSON.stringify(payload)
    });

    let data = null;
    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
      data = await response.json();
    } else {
      const text = await response.text();
      throw new Error(text || "Server không trả về dữ liệu JSON hợp lệ.");
    }

    if (!response.ok) {
      throw new Error(data.detail || "Tìm kiếm khách sạn thất bại.");
    }

    hotelResults = Array.isArray(data.items) ? data.items : [];
    currentPage = 1;

    renderHotelTable();
    renderPagination();
  } catch (error) {
    console.error("searchHotels error:", error);

    hotelTableBody.innerHTML = `
      <tr>
        <td colspan="7" class="table-empty">Không tải được danh sách khách sạn.</td>
      </tr>
    `;

    resultCount.textContent = "0 kết quả";
    paginationWrap?.classList.add("hidden");

    showToast(error.message || "Tìm kiếm thất bại.", "error");
  }
}

/* =========================================
   PHÂN TRANG
========================================= */
function getPaginatedHotels() {
  const start = (currentPage - 1) * PAGE_SIZE;
  const end = start + PAGE_SIZE;
  return hotelResults.slice(start, end);
}

function renderPagination() {
  if (!paginationWrap || !paginationNumbers || !prevPageBtn || !nextPageBtn) return;

  const totalPages = Math.ceil(hotelResults.length / PAGE_SIZE);

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
      renderHotelTable();
      renderPagination();
    });

    paginationNumbers.appendChild(btn);
  }

  prevPageBtn.disabled = currentPage === 1;
  nextPageBtn.disabled = currentPage === totalPages;
}

/* =========================================
   RENDER TABLE HOTEL
========================================= */
function renderHotelTable() {
  resultCount.textContent = `${hotelResults.length} kết quả`;

  const currentItems = getPaginatedHotels();

  if (!currentItems.length) {
    hotelTableBody.innerHTML = `
      <tr>
        <td colspan="7" class="table-empty">Không có khách sạn phù hợp.</td>
      </tr>
    `;
    return;
  }

    hotelTableBody.innerHTML = currentItems.map(item => `
    <tr>
        <td>${escapeHtml(item.hotel_id)}</td>
        <td>${escapeHtml(item.hotel_name || "—")}</td>
        <td>${escapeHtml(normalizeCityName(item.city || "—"))}</td>
        <td>${escapeHtml(formatMoney(item.min_price))}</td>
        <td>${escapeHtml(item.star_rating ?? "—")}</td>
        <td>${escapeHtml(prettySource(item.source || "—"))}</td>
        <td>
        <button class="view-btn" data-hotel-id="${item.hotel_id}" type="button">
            Xem chi tiết
        </button>
        </td>
    </tr>
    `).join("");

  /* Gắn sự kiện cho nút xem chi tiết */
  hotelTableBody.querySelectorAll(".view-btn").forEach(btn => {
    btn.addEventListener("click", () => openDetailModal(Number(btn.dataset.hotelId)));
  });
}

/* =========================================
   MỞ MODAL CHI TIẾT
========================================= */
function openDetailModal(hotelId) {
  const hotel = hotelResults.find(item => Number(item.hotel_id) === Number(hotelId));

  if (!hotel) {
    showToast("Không tìm thấy dữ liệu khách sạn.", "error");
    return;
  }

  currentHotel = hotel;
  fillDetailModal(hotel);

  detailOverlay?.classList.remove("hidden");
}

/* =========================================
   ĐỔ DỮ LIỆU VÀO MODAL CHI TIẾT
========================================= */
function fillDetailModal(hotel) {
  if (!detailHotelInfo || !detailSource || !detailAddress) return;

  detailSource.textContent = prettySource(hotel.source || "—");
  detailSource.className = "status-chip";

  detailHotelInfo.innerHTML = `
    <div class="detail-item">
      <span>Mã khách sạn</span>
      <strong>${escapeHtml(hotel.hotel_id ?? "—")}</strong>
    </div>

    <div class="detail-item wide">
      <span>Mã khách sạn từ nguồn ngoài</span>
      <strong>${escapeHtml(hotel.external_hotel_code || "Đang cập nhật")}</strong>
    </div>

    <div class="detail-item">
      <span>Tên khách sạn</span>
      <strong>${escapeHtml(hotel.hotel_name || "Đang cập nhật")}</strong>
    </div>

    <div class="detail-item">
      <span>Thành phố</span>
      <strong>${escapeHtml(normalizeCityName(hotel.city || "Đang cập nhật"))}</strong>
    </div>

    <div class="detail-item">
      <span>Quốc gia</span>
      <strong>${escapeHtml(hotel.country || "Đang cập nhật")}</strong>
    </div>

    <div class="detail-item">
      <span>Số điện thoại</span>
      <strong>${escapeHtml(hotel.phone || "Đang cập nhật")}</strong>
    </div>

    <div class="detail-item">
      <span>Email</span>
      <strong>${escapeHtml(hotel.email || "Đang cập nhật")}</strong>
    </div>

    <div class="detail-item">
      <span>Hạng sao</span>
      <strong>${escapeHtml(hotel.star_rating ?? "Đang cập nhật")}</strong>
    </div>

    <div class="detail-item">
      <span>Giá thấp nhất</span>
      <strong>${escapeHtml(formatMoney(hotel.min_price))}</strong>
    </div>

    <div class="detail-item">
      <span>Sức chứa tối đa</span>
      <strong>${escapeHtml(hotel.max_capacity ?? 0)}</strong>
    </div>

    <div class="detail-item">
      <span>Tổng số phòng trống</span>
      <strong>${escapeHtml(hotel.total_available_quantity ?? 0)}</strong>
    </div>

    <div class="detail-item">
      <span>Ngày tạo</span>
      <strong>${escapeHtml(formatDate(hotel.created_at))}</strong>
    </div>
  `;

  detailAddress.textContent = hotel.address || "Đang cập nhật";
}

/* =========================================
   ĐÓNG MODAL CHI TIẾT
========================================= */
function closeDetailModal() {
  detailOverlay?.classList.add("hidden");
  currentHotel = null;
}

/* =========================================
   XÓA HOTEL
========================================= */
async function deleteCurrentHotel() {
  if (!currentHotel || !currentHotel.hotel_id) return;

  openConfirmModal(
    `Bạn có chắc muốn xóa khách sạn "${currentHotel.hotel_name}" không? Hành động này không thể hoàn tác.`,
    async () => {
      try {
        const response = await fetchWithAuth(`${API_BASE_URL}/admin/hotels/${currentHotel.hotel_id}`, {
          method: "DELETE"
        });

        let data = null;
        const contentType = response.headers.get("content-type") || "";

        if (contentType.includes("application/json")) {
          data = await response.json();
        } else {
          const text = await response.text();
          throw new Error(text || "Server không trả về dữ liệu hợp lệ.");
        }

        if (!response.ok) {
          throw new Error(data.detail || "Xóa khách sạn thất bại.");
        }

        closeDetailModal();
        showToast(data.message || "Xóa khách sạn thành công.", "success");

        /* Load lại danh sách sau khi xóa */
        await searchHotels();
      } catch (error) {
        console.error("deleteCurrentHotel error:", error);
        showToast(error.message || "Xóa khách sạn thất bại.", "error");
      }
    }
  );
}

/* =========================================
   RESET FORM SEARCH
========================================= */
function resetSearchForm() {
  searchHotelForm?.reset();
  if (searchSortByInput) {
    searchSortByInput.value = "price_asc";
  }
}

/* =========================================
   LOGOUT
========================================= */
function handleLogout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("current_user");
window.location.href = "/";
}

/* =========================================
   GẮN SỰ KIỆN
========================================= */
function bindEvents() {
  importHotelForm?.addEventListener("submit", importHotels);
  searchHotelForm?.addEventListener("submit", searchHotels);
  resetSearchBtn?.addEventListener("click", resetSearchForm);
  logoutBtn?.addEventListener("click", handleLogout);

  closeDetailBtn?.addEventListener("click", closeDetailModal);
  deleteHotelBtn?.addEventListener("click", deleteCurrentHotel);

  /* Nút phân trang: trang trước */
  prevPageBtn?.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      renderHotelTable();
      renderPagination();
    }
  });

  /* Nút phân trang: trang sau */
  nextPageBtn?.addEventListener("click", () => {
    const totalPages = Math.ceil(hotelResults.length / PAGE_SIZE);
    if (currentPage < totalPages) {
      currentPage++;
      renderHotelTable();
      renderPagination();
    }
  });

  /* Click ra ngoài modal chi tiết thì đóng */
  detailOverlay?.addEventListener("click", (event) => {
    if (event.target === detailOverlay) {
      closeDetailModal();
    }
  });

  /* Click ra ngoài modal confirm thì đóng */
  confirmOverlay?.addEventListener("click", (event) => {
    if (event.target === confirmOverlay) {
      closeConfirmModal();
    }
  });

  /* Nhấn ESC để đóng modal */
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
   KHỞI TẠO TRANG
========================================= */
async function initAdminHotelPage() {
  if (!ensureAdminAccess()) return;

  bindEvents();

  /* Vào trang là load danh sách luôn */
  await searchHotels();
}

initAdminHotelPage();
