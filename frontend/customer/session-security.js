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

// Customer eligibility and company attachment are enforced server-side by
// /customer/overview. The browser only renders the authenticated server state.
startPortal = async function() {
    try {
        [currentUser, portalOverview] = await Promise.all([
            api("/users/me"),
            api("/customer/overview")
        ]);
        portalNavigation = portalOverview?.portal?.navigation || fallbackPortalNavigation();
        document.getElementById("login-screen").classList.add("hidden");
        document.getElementById("portal").classList.remove("hidden");
        document.getElementById("user-email").textContent = currentUser.email;
        renderPortalNavigation();
        renderAccountInfo();
        renderDashboard();
    } catch (err) {
        clearSession();
        const error = document.getElementById("login-error");
        if (error) error.textContent = err.message;
    }
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
// removed before it loads. Resume from the HttpOnly cookie instead. A missing
// cookie on the initial public login screen is expected and should stay silent.
startPortal().finally(() => {
    const error = document.getElementById("login-error");
    if (error?.textContent === "Unauthorized") error.textContent = "";
});
