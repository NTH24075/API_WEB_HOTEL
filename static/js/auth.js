const API_BASE_URL = window.location.origin;

const registerForm = document.getElementById("registerForm");
const loginForm = document.getElementById("loginForm");

const btnMe = document.getElementById("btnMe");
const btnLogout = document.getElementById("btnLogout");
const sendGoogleCredentialBtn = document.getElementById("sendGoogleCredentialBtn");

const tokenBox = document.getElementById("tokenBox");
const credentialBox = document.getElementById("credentialBox");
const resultBox = document.getElementById("resultBox");

const googleClientIdInput = document.getElementById("googleClientId");
const saveGoogleConfigBtn = document.getElementById("saveGoogleConfigBtn");
const reloadGoogleBtn = document.getElementById("reloadGoogleBtn");
const configMessage = document.getElementById("configMessage");
const googleButtonWrap = document.getElementById("googleButtonWrap");

function setResult(data) {
    resultBox.textContent = JSON.stringify(data, null, 2);
}

function setError(error) {
    resultBox.textContent = typeof error === "string"
        ? error
        : JSON.stringify(error, null, 2);
}

function saveToken(token) {
    localStorage.setItem("access_token", token);
    tokenBox.value = token;
}

function getToken() {
    return localStorage.getItem("access_token") || "";
}

function loadToken() {
    tokenBox.value = getToken();
}

function clearToken() {
    localStorage.removeItem("access_token");
    tokenBox.value = "";
}

function saveCredential(credential) {
    localStorage.setItem("google_credential", credential);
    credentialBox.value = credential;
}

function getCredential() {
    return localStorage.getItem("google_credential") || "";
}

function loadCredential() {
    credentialBox.value = getCredential();
}

function clearCredential() {
    localStorage.removeItem("google_credential");
    credentialBox.value = "";
}

function saveGoogleClientId() {
    const value = googleClientIdInput.value.trim();
    localStorage.setItem("google_client_id", value);
    configMessage.textContent = "Đã lưu Google Client ID.";
}

function loadGoogleClientId() {
    googleClientIdInput.value = localStorage.getItem("google_client_id") || "";
}

async function handleAuthResponse(response) {
    const data = await response.json();
    setResult(data);

    if (!response.ok) {
        return null;
    }

    if (data.access_token) {
        saveToken(data.access_token);
    }

    return data;
}

registerForm.addEventListener("submit", async function (e) {
    e.preventDefault();

    const payload = {
        full_name: document.getElementById("registerFullName").value.trim(),
        email: document.getElementById("registerEmail").value.trim(),
        phone: document.getElementById("registerPhone").value.trim() || null,
        password: document.getElementById("registerPassword").value.trim(),
        citizen_id: document.getElementById("registerCitizenId").value.trim() || null,
        address: document.getElementById("registerAddress").value.trim() || null,
        avatar_url: document.getElementById("registerAvatarUrl").value.trim() || null
    };

    try {
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        await handleAuthResponse(response);
    } catch (error) {
        setError(error.message);
    }
});

loginForm.addEventListener("submit", async function (e) {
    e.preventDefault();

    const payload = {
        email: document.getElementById("loginEmail").value.trim(),
        password: document.getElementById("loginPassword").value.trim()
    };

    try {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        await handleAuthResponse(response);
    } catch (error) {
        setError(error.message);
    }
});

btnMe.addEventListener("click", async function () {
    const token = getToken();

    if (!token) {
        setError("Chưa có access token. Hãy đăng nhập trước.");
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/auth/me`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        const data = await response.json();
        setResult(data);
    } catch (error) {
        setError(error.message);
    }
});

btnLogout.addEventListener("click", function () {
    clearToken();
    clearCredential();
    setResult({ message: "Đã đăng xuất ở frontend" });
});

async function sendGoogleCredentialToBackend() {
    const credential = credentialBox.value.trim();

    if (!credential) {
        setError("Chưa có Google credential.");
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/auth/google`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ credential: credential })
        });

        await handleAuthResponse(response);
    } catch (error) {
        setError(error.message);
    }
}

sendGoogleCredentialBtn.addEventListener("click", sendGoogleCredentialToBackend);

function onGoogleSuccess(response) {
    const credential = response.credential;
    saveCredential(credential);
    sendGoogleCredentialToBackend();
}

function renderGoogleButton() {
    const clientId = googleClientIdInput.value.trim();

    googleButtonWrap.innerHTML = "";

    if (!clientId) {
        configMessage.textContent = "Bạn chưa nhập Google Client ID.";
        return;
    }

    if (!window.google || !google.accounts || !google.accounts.id) {
        configMessage.textContent = "Google script chưa tải xong. Đợi vài giây rồi thử lại.";
        return;
    }

    google.accounts.id.initialize({
        client_id: clientId,
        callback: onGoogleSuccess,
        auto_select: false,
        cancel_on_tap_outside: true
    });

    const buttonDiv = document.createElement("div");
    googleButtonWrap.appendChild(buttonDiv);

    google.accounts.id.renderButton(buttonDiv, {
        theme: "outline",
        size: "large",
        text: "signin_with",
        shape: "rectangular",
        width: 300
    });

    configMessage.textContent = "Đã nạp nút Google.";
}

saveGoogleConfigBtn.addEventListener("click", saveGoogleClientId);

reloadGoogleBtn.addEventListener("click", function () {
    saveGoogleClientId();
    renderGoogleButton();
});

window.addEventListener("load", function () {
    loadToken();
    loadCredential();
    loadGoogleClientId();

    setTimeout(() => {
        if (googleClientIdInput.value.trim()) {
            renderGoogleButton();
        }
    }, 800);
});