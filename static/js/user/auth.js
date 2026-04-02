const API_BASE_URL = "http://127.0.0.1:8000";

const homePanel = document.getElementById("homePanel");
const loginPanel = document.getElementById("loginPanel");
const registerPanel = document.getElementById("registerPanel");

const openLoginBtn = document.getElementById("openLoginBtn");
const openRegisterBtn = document.getElementById("openRegisterBtn");
const backHomeBtn = document.getElementById("backHomeBtn");
const backFromRegisterBtn = document.getElementById("backFromRegisterBtn");

function hideAllPanels() {
  homePanel.classList.remove("active");
  loginPanel.classList.remove("active");
  registerPanel.classList.remove("active");
}

function showHomePanel() {
  hideAllPanels();
  homePanel.classList.add("active");
  document.body.classList.remove("login-open");
}

function showLoginPanel() {
  hideAllPanels();
  loginPanel.classList.add("active");
  document.body.classList.add("login-open");
}

function showRegisterPanel() {
  hideAllPanels();
  registerPanel.classList.add("active");
  document.body.classList.add("login-open");
}

openLoginBtn?.addEventListener("click", showLoginPanel);
openRegisterBtn?.addEventListener("click", showRegisterPanel);
backHomeBtn?.addEventListener("click", showHomePanel);
backFromRegisterBtn?.addEventListener("click", showHomePanel);

// mặc định khi vào trang
showHomePanel();

const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");

loginForm?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  try {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || "Đăng nhập thất bại");
      return;
    }
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("current_user", JSON.stringify(data.user));

    alert("Đăng nhập thành công!");
    if (data.user.role_name === "Admin") {
      window.location.href = "/admin-user-page";
    } else {
      window.location.href = "/user-info-page";
}
  } catch (err) {
    console.error(err);
    alert("Có lỗi xảy ra khi đăng nhập");
  }
});

registerForm?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    full_name: document.getElementById("registerFullName").value.trim(),
    email: document.getElementById("registerEmail").value.trim(),
    password: document.getElementById("registerPassword").value,
    phone: document.getElementById("registerPhone").value.trim() || null,
    citizen_id: document.getElementById("registerCitizenId").value.trim() || null,
    address: document.getElementById("registerAddress").value.trim() || null,
    avatar_url: document.getElementById("registerAvatarUrl").value.trim() || null,
  };

  try {
    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || "Đăng kí thất bại");
      return;
    }

    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("current_user", JSON.stringify(data.user));

    alert("Đăng kí thành công!");
    window.location.href = "/user-info-page";
  } catch (err) {
    console.error(err);
    alert("Có lỗi xảy ra khi đăng kí");
  }
});

// Google login
async function handleGoogleCredential(response) {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/google`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        credential: response.credential,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || "Đăng nhập Google thất bại");
      return;
    }

    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("current_user", JSON.stringify(data.user));

    alert("Đăng nhập Google thành công");
    window.location.href = "/user-info-page";
  } catch (err) {
    console.error(err);
    alert("Có lỗi khi đăng nhập Google");
  }
}

window.handleGoogleCredential = handleGoogleCredential;