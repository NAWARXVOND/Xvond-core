// Browser authentication uses the server-issued HttpOnly xvond_session cookie.
// Keep bearer-token support on the API for non-browser clients, but never persist
// a bearer token in JavaScript-accessible storage in the bundled portal.
localStorage.removeItem("xvond_customer_token");
token = null;

api = async function(path, options = {}) {
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {})
    };
    const response = await fetch(path, {
        ...options,
        credentials: "same-origin",
        headers
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (response.status === 401) {
        clearSession();
        throw new Error("Unauthorized");
    }
    if (!response.ok) {
        const detail = typeof data.detail === "string"
            ? data.detail
            : (data.detail?.message || "Request failed");
        throw new Error(detail);
    }
    return data;
};

login = async function() {
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const error = document.getElementById("login-error");
    error.textContent = "";
    try {
        const data = await api("/auth/login", {
            method: "POST",
            body: JSON.stringify({email, password})
        });
        if (!["owner", "admin", "manager", "employee"].includes(data.user?.role)) {
            try { await api("/auth/logout", {method: "POST", body: "{}"}); } catch (_) {}
            throw new Error("Customer account required");
        }
        token = null;
        await startPortal();
    } catch (err) {
        error.textContent = err.message;
    }
};

logout = async function() {
    try {
        await api("/auth/logout", {method: "POST", body: "{}"});
    } catch (_) {
        // Clear the browser state even when the server session has expired.
    } finally {
        clearSession();
    }
};

// app.js no longer resumes from localStorage because the legacy token is
// removed before it loads. Resume from the HttpOnly cookie instead.
startPortal();
