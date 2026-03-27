function formatMoney(value, currency = "USD") {
  if (value === null || value === undefined || value === "") return "N/A";
  const number = Number(value);
  if (Number.isNaN(number)) return `${value} ${currency}`;
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(number);
}

function createHotelCard(hotel, checkIn, adults) {
  return `
    <article class="hotel-card">
      <div class="hotel-card-image">
        <div class="image-placeholder">Hotel</div>
      </div>

      <div class="hotel-card-body">
        <div class="hotel-card-content">
          <h3>${hotel.name}</h3>
          <p>${hotel.address || "Chưa có địa chỉ"}</p>
          <div class="hotel-card-tags">
            <span class="tag">Amadeus</span>
            <span class="tag">${hotel.country_code || "N/A"}</span>
          </div>
        </div>

        <a class="primary-btn inline-btn"
           href="/hotels/${hotel.hotel_id}?check_in=${encodeURIComponent(checkIn)}&adults=${encodeURIComponent(adults)}">
          Xem chi tiết
        </a>
      </div>
    </article>
  `;
}

async function loadHotels() {
  const cityCode = document.getElementById("cityCode").value.trim();
  const checkIn = document.getElementById("checkInDate").value;
  const adults = document.getElementById("adults").value;
  const resultBox = document.getElementById("hotelResults");

  if (!cityCode) {
    alert("Nhập city code trước.");
    return;
  }

  resultBox.innerHTML = `<div class="loading-card">Đang tìm khách sạn...</div>`;

  try {
    const res = await fetch(`/api/hotels?city_code=${encodeURIComponent(cityCode)}&max_results=12`);
    const hotels = await res.json();

    if (!Array.isArray(hotels) || hotels.length === 0) {
      resultBox.innerHTML = `<div class="empty-card">Không có khách sạn nào cho city code này.</div>`;
      return;
    }

    resultBox.innerHTML = hotels.map(h => createHotelCard(h, checkIn, adults)).join("");
  } catch (error) {
    resultBox.innerHTML = `<div class="empty-card">Không tải được dữ liệu khách sạn.</div>`;
  }
}

function renderStars(count = 5) {
  return "★".repeat(Math.max(0, Math.min(5, count)));
}

function renderGallery(images) {
  const gallery = document.getElementById("gallery");

  if (!images || images.length === 0) {
    gallery.innerHTML = `<div class="gallery-main no-image">Không có ảnh</div>`;
    return;
  }

  const mainImage = images[0];
  const thumbs = images.slice(1, 5);

  gallery.innerHTML = `
    <div class="gallery-main">
      <img src="${mainImage.url}" alt="${mainImage.caption || "Hotel image"}" />
    </div>
    <div class="gallery-side">
      ${thumbs.map(img => `
        <div class="gallery-thumb">
          <img src="${img.url}" alt="${img.caption || "Hotel image"}" />
        </div>
      `).join("")}
    </div>
  `;
}

function renderSentiments(rating) {
  const box = document.getElementById("sentiments");
  const sentiments = rating?.sentiments || {};
  const entries = Object.entries(sentiments);

  if (!entries.length) {
    box.innerHTML = `<div class="muted-text">Chưa có dữ liệu đánh giá tổng hợp từ API.</div>`;
    return;
  }

  box.innerHTML = entries.map(([key, value]) => `
    <div class="sentiment-item">
      <div class="sentiment-label">${key}</div>
      <div class="sentiment-bar">
        <div class="sentiment-fill" style="width:${Math.min(value, 100)}%"></div>
      </div>
      <div class="sentiment-value">${value}</div>
    </div>
  `).join("");
}

function renderOffers(offers) {
  const wrap = document.getElementById("offers");

  if (!offers || offers.length === 0) {
    wrap.innerHTML = `
      <div class="offer-card">
        <div>
          <h3>Chưa có phòng khả dụng</h3>
          <p class="muted-text">Bạn có thể thử ngày khác hoặc khách sạn khác.</p>
        </div>
      </div>
    `;
    return;
  }

  wrap.innerHTML = offers.map(offer => `
    <article class="offer-card">
      <div class="offer-left">
        <h3>${offer.room_type || "Phòng tiêu chuẩn"}</h3>
        <p>${offer.description || "Không có mô tả"}</p>

        <div class="offer-tags">
          ${offer.capacity ? `<span class="tag">Sức chứa ${offer.capacity}</span>` : ""}
          ${offer.beds ? `<span class="tag">${offer.beds} giường</span>` : ""}
          ${offer.bed_type ? `<span class="tag">${offer.bed_type}</span>` : ""}
        </div>

        <div class="offer-policy">${offer.cancellation_policy || "Không có thông tin hủy phòng"}</div>
      </div>

      <div class="offer-right">
        <div class="price-total">${formatMoney(offer.price_total, offer.currency)}</div>
        <div class="muted-text">Tổng giá</div>
        <button class="primary-btn inline-btn">Chọn phòng</button>
      </div>
    </article>
  `).join("");
}

async function loadHotelDetail() {
  const body = document.body;
  const hotelId = body.dataset.hotelId;
  const checkIn = body.dataset.checkIn;
  const adults = body.dataset.adults;

  try {
    const res = await fetch(`/api/hotels/${hotelId}?check_in=${encodeURIComponent(checkIn)}&adults=${encodeURIComponent(adults)}`);
    const data = await res.json();

    document.getElementById("hotelName").textContent = data.name || "Unknown hotel";
    document.getElementById("hotelStars").textContent = renderStars(5);
    document.getElementById("hotelAddress").textContent = data.address || "Chưa có địa chỉ";
    document.getElementById("hotelDescription").textContent = data.description || "Không có mô tả";

    const amenities = document.getElementById("amenities");
    amenities.innerHTML = (data.amenities || []).length
      ? data.amenities.map(item => `<span class="chip">${item}</span>`).join("")
      : `<span class="muted-text">Chưa có tiện nghi</span>`;

    const ratingBox = document.getElementById("ratingBox");
    if (data.rating?.overall) {
      ratingBox.innerHTML = `
        <div class="rating-score">${data.rating.overall}</div>
        <div>
          <div class="rating-label">Rất tốt</div>
          <div class="muted-text">${data.rating.reviews_count || 0} đánh giá tổng hợp</div>
        </div>
      `;
    } else {
      ratingBox.innerHTML = `
        <div class="rating-empty">Chưa có điểm</div>
      `;
    }

    document.getElementById("priceFrom").textContent = data.price_from
      ? formatMoney(data.price_from, data.currency)
      : "N/A";

    document.getElementById("bookingSummary").textContent =
      `Check-in ${data.check_in} · ${data.adults} người lớn`;

    renderGallery(data.images || []);
    renderSentiments(data.rating || {});
    renderOffers(data.offers || []);

    document.getElementById("detailLoading").classList.add("hidden");
    document.getElementById("hotelDetail").classList.remove("hidden");
  } catch (error) {
    document.getElementById("detailLoading").innerHTML =
      "Không tải được chi tiết khách sạn.";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;

  if (page === "hotel-list") {
    document.getElementById("searchBtn").addEventListener("click", loadHotels);
    loadHotels();
  }

  if (page === "hotel-detail") {
    loadHotelDetail();
  }
});