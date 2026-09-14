(() => {
    // The bundled customer portal authenticates exclusively with the HttpOnly
    // session cookie set by /auth/login. Keep bearer tokens out of browser storage.
    localStorage.removeItem("xvond_customer_token");
    token = null;

    let refreshTimer = null;

    function portalIsActive() {
        const portal = document.getElementById("portal");
        return Boolean(portal && !portal.classList.contains("hidden"));
    }

    function showSessionExpiredMessage() {
        const error = document.getElementById("login-error");
        if (error) error.textContent = "Session expired. Please sign in again.";
    }

    async function refreshSessionCookie() {
        if (!portalIsActive()) return false;
        try {
            const response = await fetch("/auth/refresh", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                credentials: "same-origin",
                body: "{}"
            });
            if (response.status === 401) {
                clearSession();
                showSessionExpiredMessage();
                return false;
            }
            return response.ok;
        } catch (_) {
            // A temporary network failure should not destroy a still-valid session.
            return false;
        }
    }

    function ensureSessionKeepAlive() {
        if (!refreshTimer) {
            // Default access-token lifetime is 60 minutes. Refresh well before expiry
            // while the customer portal is actively open.
            refreshTimer = window.setInterval(refreshSessionCookie, 20 * 60 * 1000);
        }
    }

    window.clearSession = function clearSessionCookieOnly() {
        localStorage.removeItem("xvond_customer_token");
        token = null;
        currentUser = null;
        portalOverview = null;
        portalNavigation = [];
        agents = [];
        chatConversationId = null;
        document.getElementById("portal")?.classList.add("hidden");
        document.getElementById("login-screen")?.classList.remove("hidden");
    };

    window.api = async function cookieApi(path, options = {}) {
        const headers = {
            "Content-Type": "application/json",
            ...(options.headers || {})
        };
        const response = await fetch(path, {
            ...options,
            headers,
            credentials: "same-origin"
        });
        let data = {};
        try { data = await response.json(); } catch (_) {}
        if (response.status === 401) {
            clearSession();
            showSessionExpiredMessage();
            throw new Error("Session expired");
        }
        if (!response.ok) {
            const detail = typeof data.detail === "string"
                ? data.detail
                : (data.detail?.message || "Request failed");
            throw new Error(detail);
        }
        return data;
    };

    window.login = async function cookieLogin() {
        const email = document.getElementById("login-email").value.trim();
        const password = document.getElementById("login-password").value;
        const error = document.getElementById("login-error");
        error.textContent = "";
        try {
            const response = await fetch("/auth/login", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                credentials: "same-origin",
                body: JSON.stringify({email, password})
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.detail || "Login failed");
            // access_token may remain in the API response for external API clients,
            // but the browser portal deliberately ignores it.
            await startPortal();
            ensureSessionKeepAlive();
        } catch (err) {
            error.textContent = err.message;
        }
    };

    window.logout = async function cookieLogout() {
        try {
            await api("/auth/logout", {method: "POST", body: "{}"});
        } catch (_) {
            // Local session cleanup must happen even when the server session expired.
        } finally {
            clearSession();
        }
    };

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible" && portalIsActive()) {
            refreshSessionCookie();
        }
    });

    ensureSessionKeepAlive();
})();
