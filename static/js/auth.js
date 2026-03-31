const API_BASE_URL = window.location.origin;

const homePanel = document.getElementById("homePanel");
const loginPanel = document.getElementById("loginPanel");
const openLoginBtn = document.getElementById("openLoginBtn");
const backHomeBtn = document.getElementById("backHomeBtn");
const loginForm = document.getElementById("loginForm");
const cityCodeInput = document.getElementById("cityCode");
const checkInDateInput = document.getElementById("checkInDate");
const adultsSelect = document.getElementById("adults");
const destGrid = document.getElementById("destGrid");
const googleLoginBtn = document.getElementById("googleLoginBtn");
const registerPanel = document.getElementById("registerPanel");
const openRegisterBtn = document.getElementById("openRegisterBtn");
const backFromRegisterBtn = document.getElementById("backFromRegisterBtn");
const registerForm = document.getElementById("registerForm");


(function setDefaultCheckInDate() {
  const today = new Date().toISOString().slice(0, 10);
  if (checkInDateInput) {
    checkInDateInput.value = today;
  }
})();



window.handleGoogleCredential = async function (response) {
  const credential = response.credential;

  try {
    const res = await fetch("http://127.0.0.1:8000/auth/google", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        credential: credential
      })
    });

    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || "Google login thất bại");
      return;
    }

    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("current_user", JSON.stringify(data.user));

    alert("Đăng nhập Google thành công!");
    window.location.href = "/";
  } catch (err) {
    console.error(err);
    alert("Lỗi kết nối server");
  }
};

function handleGoogleLogin() {
  window.location.href = `${API_BASE_URL}/auth/google`;
}

function showLoginPanel() {
  document.body.classList.add("login-open");
  homePanel?.classList.remove("active");
  loginPanel?.classList.add("active");
}

function showRegisterPanel() {
  document.body.classList.add("login-open");
  homePanel?.classList.remove("active");
  loginPanel?.classList.remove("active");
  registerPanel?.classList.add("active");
}

function showHomePanel() {
  document.body.classList.remove("login-open");
  loginPanel?.classList.remove("active");
  registerPanel?.classList.remove("active");
  homePanel?.classList.add("active");
}


function goSearch(cityOverride) {
  const city = cityOverride || cityCodeInput?.value?.trim() || "HAN";
  const checkIn = checkInDateInput?.value || new Date().toISOString().slice(0, 10);
  const adults = adultsSelect?.value || "2";

  if (!city) {
    alert("Vui lòng nhập điểm đến.");
    return;
  }

  window.location.href = `/hotels?city=${encodeURIComponent(city)}&check_in=${encodeURIComponent(checkIn)}&adults=${encodeURIComponent(adults)}`;
}

async function handleLogin(event) {
  event.preventDefault();

  const email = document.getElementById("loginEmail")?.value.trim();
  const password = document.getElementById("loginPassword")?.value;

  if (!email || !password) {
    alert("Vui lòng nhập đầy đủ email và mật khẩu.");
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        email,
        password
      })
    });

    const data = await response.json();

    if (!response.ok) {
      alert(data.detail || "Đăng nhập thất bại.");
      return;
    }

    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("current_user", JSON.stringify(data.user));

    alert("Đăng nhập thành công!");
    window.location.reload();
  } catch (error) {
    console.error("Login error:", error);
    alert("Không thể kết nối tới server.");
  }
}


openLoginBtn?.addEventListener("click", showLoginPanel);
backHomeBtn?.addEventListener("click", showHomePanel);
loginForm?.addEventListener("submit", handleLogin);

async function handleRegister(event) {
  event.preventDefault();

  const payload = {
    full_name: document.getElementById("registerFullName")?.value.trim(),
    email: document.getElementById("registerEmail")?.value.trim(),
    password: document.getElementById("registerPassword")?.value,
    phone: document.getElementById("registerPhone")?.value.trim() || null,
    citizen_id: document.getElementById("registerCitizenId")?.value.trim() || null,
    address: document.getElementById("registerAddress")?.value.trim() || null,
    avatar_url: document.getElementById("registerAvatarUrl")?.value.trim() || null
  };

  if (!payload.full_name || !payload.email || !payload.password) {
    alert("Vui lòng nhập họ tên, email và mật khẩu.");
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      alert(data.detail || "Đăng kí thất bại.");
      return;
    }

    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("current_user", JSON.stringify(data.user));

    alert("Đăng kí thành công!");
    window.location.href = "/";
  } catch (error) {
    console.error("Register error:", error);
    alert("Không thể kết nối tới server.");
  }
}

openRegisterBtn?.addEventListener("click", showRegisterPanel);
backFromRegisterBtn?.addEventListener("click", showHomePanel);
registerForm?.addEventListener("submit", handleRegister);


cityCodeInput?.addEventListener("keydown", function (event) {
  if (event.key === "Enter") {
    goSearch();
  }
});

destGrid?.addEventListener("click", function (event) {
  const card = event.target.closest(".dest-card[data-city]");
  if (!card) return;

  const city = card.dataset.city;
  const checkIn = new Date().toISOString().slice(0, 10);
  const adults = adultsSelect?.value || "2";

  window.location.href = `/hotels?city=${encodeURIComponent(city)}&check_in=${encodeURIComponent(checkIn)}&adults=${encodeURIComponent(adults)}`;
});


googleLoginBtn?.addEventListener("click", handleGoogleLogin);