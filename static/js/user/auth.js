const API_BASE_URL = window.location.origin;

const homePanel = document.getElementById("homePanel");
const loginPanel = document.getElementById("loginPanel");
const registerPanel = document.getElementById("registerPanel");

const backHomeBtn = document.getElementById("backHomeBtn");
const backFromRegisterBtn = document.getElementById("backFromRegisterBtn");
const topbarActions = document.getElementById("topbarActions");

const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");

function hideAllPanels() {
  homePanel?.classList.remove("active");
  loginPanel?.classList.remove("active");
  registerPanel?.classList.remove("active");
}

function showHomePanel() {
  hideAllPanels();
  homePanel?.classList.add("active");
  document.body.classList.remove("login-open");
}

function showLoginPanel() {
  hideAllPanels();
  loginPanel?.classList.add("active");
  document.body.classList.add("login-open");
}

function showRegisterPanel() {
  hideAllPanels();
  registerPanel?.classList.add("active");
  document.body.classList.add("login-open");
}

function getStoredUser() {
  return JSON.parse(localStorage.getItem("current_user") || "null");
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

function handleLogout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("current_user");
  renderToolbarState();
  showHomePanel();
}

function renderGuestToolbar() {
  if (!topbarActions) return;

  topbarActions.innerHTML = `
    <button class="topbar-login" id="openLoginBtn" type="button">Đăng nhập</button>
    <button class="topbar-cta" id="openRegisterBtn" type="button">Đăng kí</button>
  `;

  document.getElementById("openLoginBtn")?.addEventListener("click", showLoginPanel);
  document.getElementById("openRegisterBtn")?.addEventListener("click", showRegisterPanel);
}

function renderUserToolbar(user) {
  if (!topbarActions) return;

  topbarActions.innerHTML = `
    <button class="user-avatar-btn" id="goUserInfoBtn" type="button" title="Thông tin tài khoản">
      <img src="${getAvatarSrc(user?.avatar_url)}" alt="avatar người dùng">
    </button>
    <button class="topbar-login topbar-logout" id="logoutBtn" type="button">Đăng xuất</button>
  `;

  document.getElementById("goUserInfoBtn")?.addEventListener("click", () => {
    window.location.href = "/user-info-page";
  });

  document.getElementById("logoutBtn")?.addEventListener("click", handleLogout);
}

function renderToolbarState() {
  const token = localStorage.getItem("access_token");
  const user = getStoredUser();

  if (token && user) {
    renderUserToolbar(user);
  } else {
    renderGuestToolbar();
  }
}

backHomeBtn?.addEventListener("click", showHomePanel);
backFromRegisterBtn?.addEventListener("click", showHomePanel);

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
      return;
    }

    renderToolbarState();
    showHomePanel();
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

    if (data.user.role_name === "Admin") {
      window.location.href = "/admin-user-page";
      return;
    }

    renderToolbarState();
    showHomePanel();
  } catch (err) {
    console.error(err);
    alert("Có lỗi xảy ra khi đăng kí");
  }
});

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

    if (data.user.role_name === "Admin") {
      window.location.href = "/admin-user-page";
      return;
    }

    renderToolbarState();
    showHomePanel();
  } catch (err) {
    console.error(err);
    alert("Có lỗi khi đăng nhập Google");
  }
}

window.handleGoogleCredential = handleGoogleCredential;

renderToolbarState();
showHomePanel();