// ─── Utilities ────────────────────────────────────────────────────────────────

function formatMoney(value, currency = "VND") {
  if (value == null || value === "") return "N/A";
  const n = Number(value);
  if (Number.isNaN(n)) return `${value} ${currency}`;
  return new Intl.NumberFormat("vi-VN", {
    style: "currency", currency, maximumFractionDigits: 0,
  }).format(n);
}

function renderStars(count) {
  const n = Math.round(Number(count) || 0);
  return "★".repeat(Math.max(0, Math.min(5, n)));
}

// ─── City alias ────────────────────────────────────────────────────────────────

const CITY_NAMES = {
  BKK: "Bangkok", PAR: "Paris", SGN: "Ho Chi Minh City", HAN: "Hanoi",
  DAD: "Da Nang", NHA: "Nha Trang", DLI: "Da Lat", HUI: "Hue",
  SIN: "Singapore", TYO: "Tokyo", OSA: "Osaka", ICN: "Seoul",
  HKG: "Hong Kong", LON: "London", NYC: "New York", LAX: "Los Angeles",
  SFO: "San Francisco", BJS: "Beijing", SHA: "Shanghai", KUL: "Kuala Lumpur",
};
function resolveCityName(raw) {
  const up = raw.trim().toUpperCase();
  return CITY_NAMES[up] || raw.trim();
}

// ─── Weather — gọi qua backend /api/weather (giấu API key) ───────────────────

function getWeatherIconEmoji(iconCode) {
  if (!iconCode) return "🌡";
  const main = iconCode.replace(/[dn]$/, "");
  const map = {
    "01": "☀️", "02": "⛅", "03": "☁️", "04": "☁️",
    "09": "🌧", "10": "🌦", "11": "⛈", "13": "❄️", "50": "🌫",
  };
  return map[main] ?? "🌡";
}
async function fetchWeatherFromBackend({ city, cityCode, lat, lon, checkIn } = {}) {
  try {
    const params = new URLSearchParams({ lang: "vi" });

    if (checkIn) params.set("check_in", checkIn);

    if (lat != null && lon != null) {
      params.set("lat", lat);
      params.set("lon", lon);
    } else if (city) {
      params.set("city", city);
    } else if (cityCode) {
      params.set("city_code", cityCode);
    }

    const res = await fetch(`/api/weather?${params}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (e) {
    console.warn("Weather fetch error:", e.message);
    return null;
  }
}
function buildWeatherHTML(w) {
  if (!w || !Array.isArray(w.days) || !w.days.length) {
    return `<div class="weather-error">Không tải được dự báo thời tiết 3 ngày.</div>`;
  }

  const cards = w.days.map(day => {
    const iconImg = day.icon_url
      ? `<img src="${day.icon_url}" alt="${day.description}" width="42" height="42" />`
      : `<span style="font-size:30px">${getWeatherIconEmoji(day.icon_code)}</span>`;

    const dateLabel = new Date(day.date).toLocaleDateString("vi-VN", {
      weekday: "short",
      day: "2-digit",
      month: "2-digit",
    });

    return `
      <div class="forecast-day">
        <div class="forecast-date">${dateLabel}</div>
        <div class="forecast-icon">${iconImg}</div>
        <div class="forecast-temp">${day.temp_min}° - ${day.temp_max}°</div>
        <div class="forecast-desc" style="text-transform:capitalize">${day.description}</div>
        <div class="forecast-meta">💧 ${day.humidity ?? "--"}%</div>
      </div>
    `;
  }).join("");

  return `
    <div class="weather-content">
      <div class="weather-city" style="margin-bottom:10px">
        ${w.city}${w.country ? ", " + w.country : ""}
      </div>
      <div class="forecast-grid">
        ${cards}
      </div>
    </div>
  `;
}
async function loadWeatherSidebar(cityRaw, checkIn) {
  const container = document.getElementById("weatherContent");
  if (!container) return;
  container.innerHTML = `
    <div class="weather-loading">
      <div class="spinner" style="border-color:rgba(255,255,255,.3);border-top-color:white"></div>
      <span>Đang tải dự báo 3 ngày…</span>
    </div>`;

  const data = await fetchWeatherFromBackend({
    cityCode: cityRaw,
    checkIn: checkIn,
  });

  container.innerHTML = buildWeatherHTML(data);
}
async function loadWeatherDetail(hotelData) {
  const card    = document.getElementById("detailWeather");
  const content = document.getElementById("detailWeatherContent");
  if (!card || !content) return;
  const data = await fetchWeatherFromBackend({
    lat: hotelData.latitude,
    lon: hotelData.longitude,
  });
  if (data) {
    card.style.display = "block";
    content.innerHTML  = buildWeatherHTML(data);
  }
}

// ─── Enrich hotels với mock stars / price / amenities cho filter ──────────────
// (Geoapify /v2/places không trả về các trường này trong list view)

function enrichHotels(hotels) {
  return hotels.map((h) => ({
    ...h,
    _stars: h.stars ?? 3,
    _price: h.price_from ?? 0,
    _amenities: h.amenities_preview ?? [],
  }));
}

// ─── Filter logic (client-side, áp dụng trên allHotels) ──────────────────────

function getFilters() {
  const budgetMax = Number(document.getElementById("budgetRange")?.value ?? 5000000);

  // Star: các checkbox đang checked, bỏ "all"
  const starChecks = [...document.querySelectorAll("#starFilter input[type=checkbox]:checked")]
    .map(x => x.value)
    .filter(v => v !== "all");

  // Amenity
  const amenChecks = [...document.querySelectorAll("#amenityFilter input[type=checkbox]:checked")]
    .map(x => x.value);

  return { budgetMax, starChecks, amenChecks };
}

function applyFilters(hotels) {
  const { budgetMax, starChecks, amenChecks } = getFilters();
  const sort = document.getElementById("sortSelect")?.value ?? "default";

  let list = hotels.filter(h => {
    // 1. Budget
    if (h._price > budgetMax) return false;

    // 2. Stars — nếu không chọn star nào thì bỏ qua filter sao
    if (starChecks.length > 0 && !starChecks.includes(String(h._stars))) return false;

    // 3. Amenities — phải có TẤT CẢ các tiện nghi đã tick
    if (amenChecks.length > 0) {
      if (!amenChecks.every(a => h._amenities.includes(a))) return false;
    }

    return true;
  });

  // Sort
  switch (sort) {
    case "price-asc":  list = [...list].sort((a, b) => a._price - b._price); break;
    case "price-desc": list = [...list].sort((a, b) => b._price - a._price); break;
    case "name-asc":   list = [...list].sort((a, b) => a.name.localeCompare(b.name)); break;
  }

  return list;
}

// ─── Hotel card HTML ──────────────────────────────────────────────────────────

const AMEN_LABELS = {
  wifi: "📶 Wi-Fi", pool: "🏊 Hồ bơi", ac: "❄️ AC",
  parking: "🅿️ Parking", gym: "🏋️ Gym", spa: "💆 Spa",
  restaurant: "🍽 Nhà hàng", pets: "🐾 Thú cưng",
};

function createHotelCard(hotel, checkIn, adults, idx) {
  const delay = Math.min(idx * 60, 600);
  const thumb = hotel.thumbnail
    ? `<img src="${hotel.thumbnail}" alt="${hotel.name}" loading="lazy"/>`
    : `<div class="image-placeholder">🏨</div>`;

  const starsHTML = "★".repeat(hotel._stars) + `<span style="color:#d1d5db">${"★".repeat(5 - hotel._stars)}</span>`;
  const country = hotel.country_code
    ? `<span class="hotel-country-tag">${hotel.country_code}</span>` : "";
  const amenPreview = hotel._amenities.slice(0, 4).map(a => `<span class="amenity-icon">${a}</span>`).join("");
  return `
    <article class="hotel-card" style="animation-delay:${delay}ms">
      <div class="hotel-card-image">${thumb}</div>

      <div class="hotel-card-body">
        <h3 title="${hotel.name}">${hotel.name}</h3>
        <div class="hotel-location">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
            <circle cx="12" cy="9" r="2.5"/>
          </svg>
          ${hotel.address || "Chưa có địa chỉ"}
        </div>
        <div class="hotel-highlights" style="margin-top:6px;display:flex;align-items:center;gap:8px">
          ${country}
          <span class="stars" style="font-size:14px;letter-spacing:1px">${starsHTML}</span>
        </div>
        <div class="hotel-amenities-preview">${amenPreview}</div>
      </div>

      <div class="hotel-card-price">
        <div>
          <div class="price-night">Giá từ / đêm</div>
          <div class="price-value">${formatMoney(hotel._price, "VND")}</div>
          <div class="price-note">Đã bao gồm thuế (demo)</div>
        </div>
        <div>
          <div class="rating-badge">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
            ${hotel._stars}.0
          </div>
          <a class="card-detail-btn" style="margin-top:8px;display:flex"
             href="/hotels/${hotel.hotel_id}?check_in=${encodeURIComponent(checkIn)}&adults=${encodeURIComponent(adults)}">
            Xem chi tiết →
          </a>
        </div>
      </div>
    </article>`;
}

// ─── Master hotel list ────────────────────────────────────────────────────────

let allHotels = [];

function renderResults(checkIn, adults) {
  const resultBox = document.getElementById("hotelResults");
  const topbar    = document.getElementById("resultsTopbar");
  const countEl   = document.getElementById("resultsCount");

  checkIn = checkIn || document.getElementById("checkInDate")?.value || "2026-04-08";
  adults  = adults  || document.getElementById("adults")?.value      || "2";

  const filtered = applyFilters(allHotels);
  topbar.style.display = "flex";
  countEl.innerHTML = `<strong>${filtered.length}</strong> / ${allHotels.length} khách sạn`;

  if (!filtered.length) {
    resultBox.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <p>Không có khách sạn khớp bộ lọc.<br>
           <button class="ghost-btn" style="width:auto;padding:8px 18px;margin-top:10px" onclick="resetFilters()">
             Xóa bộ lọc
           </button></p>
      </div>`;
    return;
  }
  resultBox.innerHTML = filtered.map((h, i) => createHotelCard(h, checkIn, adults, i)).join("");
}

function resetFilters() {
  document.querySelectorAll("#starFilter input[type=checkbox]").forEach(cb => {
    cb.checked = (cb.value === "all");
  });
  document.querySelectorAll("#amenityFilter input[type=checkbox]").forEach(cb => { cb.checked = false; });
  const range = document.getElementById("budgetRange");
  if (range) { range.value = range.max; updateBudgetLabel(Number(range.max)); }
  const sortSel = document.getElementById("sortSelect");
  if (sortSel) sortSel.value = "default";
  renderResults();
}

async function loadHotels() {
  const raw       = document.getElementById("cityCode").value.trim();
  const checkIn   = document.getElementById("checkInDate").value;
  const adults    = document.getElementById("adults").value;
  const resultBox = document.getElementById("hotelResults");
  const topbar    = document.getElementById("resultsTopbar");

  if (!raw) { alert("Vui lòng nhập city code hoặc tên thành phố."); return; }

  const cityName = resolveCityName(raw);
  resultBox.innerHTML = `<div class="loading-card"><div class="spinner"></div><span>Đang tìm khách sạn tại <strong>${cityName}</strong>…</span></div>`;
  topbar.style.display = "none";

  // Tải thời tiết song song
  loadWeatherSidebar(raw, checkIn);

  try {
    const res = await fetch(`/api/hotels?city_code=${encodeURIComponent(raw)}&max_results=12`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const raw_hotels = await res.json();

    if (!Array.isArray(raw_hotels) || !raw_hotels.length) {
      resultBox.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <p>Không tìm thấy khách sạn cho "<strong>${cityName}</strong>".<br>Thử: BKK, HAN, SGN, PAR, TYO…</p>
        </div>`;
      return;
    }

    allHotels = enrichHotels(raw_hotels);
    renderResults(checkIn, adults);
  } catch (err) {
    resultBox.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><p>Lỗi: ${err.message}</p></div>`;
  }
}

// ─── Budget range ─────────────────────────────────────────────────────────────

function updateBudgetLabel(value) {
  const el = document.getElementById("budgetMax");
  if (!el) return;
  el.textContent = value >= 5000000 ? "₫5.000.000+" : formatMoney(value, "VND");
}

function initBudgetRange() {
  const range = document.getElementById("budgetRange");
  if (!range) return;
  range.addEventListener("input", () => {
    updateBudgetLabel(Number(range.value));
    if (allHotels.length) renderResults();
  });
}

// ─── Star filter: "Tất cả" exclusive toggle ───────────────────────────────────

function initStarFilter() {
  const allCb  = document.querySelector("#starFilter input[value='all']");
  const others = [...document.querySelectorAll("#starFilter input:not([value='all'])")];

  allCb?.addEventListener("change", () => {
    if (allCb.checked) others.forEach(cb => { cb.checked = false; });
    if (allHotels.length) renderResults();
  });
  others.forEach(cb => {
    cb.addEventListener("change", () => {
      // Nếu không còn star nào được chọn, tự bật lại "Tất cả"
      const anyChecked = others.some(o => o.checked);
      if (allCb) allCb.checked = !anyChecked;
      if (allHotels.length) renderResults();
    });
  });
}

// ─── Amenity filter: live filter ──────────────────────────────────────────────

function initAmenityFilter() {
  document.querySelectorAll("#amenityFilter input[type=checkbox]").forEach(cb => {
    cb.addEventListener("change", () => {
      if (allHotels.length) renderResults();
    });
  });
}

// ─── Detail page ──────────────────────────────────────────────────────────────

function renderGallery(images) {
  const gallery = document.getElementById("gallery");
  if (!images?.length) {
    gallery.innerHTML = `<div class="gallery-main no-image">📷 Không có ảnh</div>`;
    return;
  }
  const [main, ...rest] = images;
  gallery.innerHTML = `
    <div class="gallery-main"><img src="${main.url}" alt="${main.caption || "Hotel"}"/></div>
    <div class="gallery-side">
      ${rest.slice(0, 4).map(img =>
        `<div class="gallery-thumb"><img src="${img.url}" alt="${img.caption || "Hotel"}"/></div>`
      ).join("")}
    </div>`;
}

function renderSentiments(rating) {
  const box     = document.getElementById("sentiments");
  const entries = Object.entries(rating?.sentiments || {});
  if (!entries.length) {
    box.innerHTML = `<div class="muted-text">Chưa có dữ liệu đánh giá từ API.</div>`;
    return;
  }
  box.innerHTML = entries.map(([key, val]) => `
    <div class="sentiment-item">
      <div class="sentiment-label">${key}</div>
      <div class="sentiment-bar"><div class="sentiment-fill" style="width:${Math.min(val,100)}%"></div></div>
      <div class="sentiment-value">${val}</div>
    </div>`).join("");
}

function renderOffers(offers) {
  const wrap = document.getElementById("offers");
  if (!offers?.length) {
    wrap.innerHTML = `<div class="offer-card"><div><h3>Chưa có phòng</h3><p class="muted-text">Thử ngày khác.</p></div></div>`;
    return;
  }
  wrap.innerHTML = offers.map(o => `
    <article class="offer-card">
      <div class="offer-left">
        <h3>${o.room_type || "Phòng tiêu chuẩn"}</h3>
        <p>${o.description || ""}</p>
        <div class="offer-tags">
          ${o.capacity     ? `<span class="tag">👥 ${o.capacity} người</span>`  : ""}
          ${o.beds         ? `<span class="tag">🛏 ${o.beds} giường</span>`     : ""}
          ${o.bed_type     ? `<span class="tag">${o.bed_type}</span>`           : ""}
          ${o.payment_type ? `<span class="tag">${o.payment_type}</span>`       : ""}
        </div>
        <div class="offer-policy">✅ ${o.cancellation_policy || "Xem chính sách hủy"}</div>
      </div>
      <div class="offer-right">
        <div class="price-total">${formatMoney(o.price_total, o.currency)}</div>
        <div class="muted-text" style="font-size:12px">/ đêm · tổng giá</div>
        <a class="inline-btn">Chọn phòng</a>
      </div>
    </article>`).join("");
}

async function loadHotelDetail() {
  const { hotelId, checkIn, adults } = document.body.dataset;
  try {
    const res  = await fetch(`/api/hotels/${hotelId}?check_in=${encodeURIComponent(checkIn)}&adults=${encodeURIComponent(adults)}`);
    const data = await res.json();

    document.getElementById("hotelName").textContent         = data.name    || "Unknown hotel";
    document.getElementById("hotelStars").textContent =  renderStars(data.rating?.overall || 0);
    document.getElementById("addressText").textContent       = data.address || "Chưa có địa chỉ";
    document.getElementById("hotelDescription").textContent  = data.description || "Không có mô tả.";

    const amenEl = document.getElementById("amenities");
    amenEl.innerHTML = data.amenities?.length
      ? data.amenities.map(a => `<span class="chip">${a}</span>`).join("")
      : `<span class="muted-text">Chưa có tiện nghi</span>`;

    const ratingBox = document.getElementById("ratingBox");
    ratingBox.innerHTML = data.rating?.overall
      ? `<div class="rating-score">${data.rating.overall}</div>
         <div>
           <div class="rating-label">Rất tốt</div>
           <div class="rating-sub">${data.rating.reviews_count || 0} đánh giá</div>
         </div>`
      : `<div class="rating-empty">Chưa có điểm đánh giá</div>`;

    document.getElementById("priceFrom").textContent =
      data.price_from ? formatMoney(data.price_from, data.currency) : "N/A";
    document.getElementById("bookingSummary").textContent =
      `Check-in ${data.check_in} · ${data.adults} người lớn`;

    renderGallery(data.images  || []);
    renderSentiments(data.rating || {});
    renderOffers(data.offers   || []);
    loadWeatherDetail(data);

    document.getElementById("detailLoading").classList.add("hidden");
    document.getElementById("hotelDetail").classList.remove("hidden");

    // Khởi tạo bản đồ Mapbox — gọi sau khi panel đã visible
    initMap(data.latitude, data.longitude, data.name, data.address);

  } catch (err) {
    document.getElementById("detailLoading").innerHTML =
      `<div class="empty-state"><div class="empty-icon"></div><p>Không tải được chi tiết: ${err.message}</p></div>`;
  }
}

const MAPBOX_TOKEN = document.body.dataset.mapboxToken || "";
function initMap(lat, lon, hotelName, address) {
  const mapEl       = document.getElementById("hotelMap");
  const placeholder = document.getElementById("mapPlaceholder");
  const footer      = document.getElementById("mapFooter");
  const addrLabel   = document.getElementById("mapAddressLabel");
  const dirLink     = document.getElementById("mapDirectionLink");

  if (!mapEl || lat == null || lon == null) {
    if (placeholder) placeholder.innerHTML = `
      <div class="map-placeholder-inner">
        <span style="font-size:28px">📍</span>
        <span style="color:#94a3b8;font-size:13px">Không có tọa độ</span>
      </div>`;
    return;
  }

  if (!MAPBOX_TOKEN) {
    if (placeholder) placeholder.innerHTML = `
      <div class="map-placeholder-inner">
        <span style="font-size:28px">🗺️</span>
        <span style="color:#94a3b8;font-size:13px">Thiếu MAPBOX_TOKEN trong .env</span>
      </div>`;
    return;
  }

  placeholder.style.display = "none";
  mapEl.style.display = "block";

  mapboxgl.accessToken = MAPBOX_TOKEN;

  const map = new mapboxgl.Map({
    container: "hotelMap",
    style: "mapbox://styles/mapbox/streets-v12",
    center: [lon, lat],
    zoom: 15,
    attributionControl: false,
  });

  map.addControl(new mapboxgl.AttributionControl({ compact: true }));
  map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "bottom-right");

  const markerEl = document.createElement("div");
  markerEl.className = "hotel-marker";

  new mapboxgl.Marker({ element: markerEl, anchor: "bottom" })
    .setLngLat([lon, lat])
    .setPopup(
      new mapboxgl.Popup({ offset: 28, closeButton: false, maxWidth: "220px" })
        .setHTML(`
          <div style="font-family:'DM Sans',sans-serif;padding:4px 2px">
            <div style="font-weight:700;font-size:13px;color:#1a202c;margin-bottom:2px">
              🏨 ${hotelName || "Khách sạn"}
            </div>
            <div style="font-size:12px;color:#718096;line-height:1.5">${address || ""}</div>
          </div>
        `)
    )
    .addTo(map);

  map.on("load", () => {
    document.querySelector(".mapboxgl-marker")?.click();
  });

  if (footer) {
    footer.style.display = "flex";
    if (addrLabel) {
      addrLabel.textContent = address
        ? address.split(",").slice(0, 2).join(",")
        : `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
    }
    if (dirLink) {
      dirLink.href = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`;
    }
  }
}
// ─── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;

  if (page === "hotel-list") {
    initBudgetRange();
    initStarFilter();
    initAmenityFilter();

    document.getElementById("searchBtn").addEventListener("click", loadHotels);
    document.getElementById("cityCode").addEventListener("keydown", e => {
      if (e.key === "Enter") loadHotels();
    });
    document.getElementById("applyFilter")?.addEventListener("click", () => {
      if (allHotels.length) renderResults();
    });
    document.getElementById("sortSelect")?.addEventListener("change", () => {
      if (allHotels.length) renderResults();
    });
    document.getElementById("checkInDate")?.addEventListener("change", () => {
      const raw = document.getElementById("cityCode")?.value?.trim();
      const checkIn = document.getElementById("checkInDate")?.value;
      if (raw && checkIn) {
        loadWeatherSidebar(raw, checkIn);
      }
    });
    loadHotels();
  }

  if (page === "hotel-detail") {
    loadHotelDetail();
  }
});




// Lấy user_id từ localStorage (tạm thời hardcode nếu chưa có)
function getUserId() {
    let userId = localStorage.getItem("user_id");
    if (!userId) {
        userId = 1; // tạm thời dùng user_id = 1
        localStorage.setItem("user_id", userId);
    }
    return userId;
}

async function addFavorite(hotelId) {
    const userId = getUserId();

    try {
        const response = await fetch("/api/favorites", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                user_id: Number(userId),
                hotel_id: hotelId
            })
        });

        const text = await response.text();

        let data;
        try {
            data = JSON.parse(text);
        } catch {
            data = { detail: text };
        }

        if (!response.ok) {
            alert("Lỗi: " + (data.detail || "Không xác định"));
            console.error("Server error:", data);
            return;
        }

        alert(data.message);
        console.log("✅ Đã thêm yêu thích:", data);

    } catch (error) {
        console.error("Lỗi khi thêm yêu thích:", error);
        alert("Có lỗi xảy ra");
    }
}