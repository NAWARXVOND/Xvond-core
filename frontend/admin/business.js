let businessCompanyId = null;


function installBusinessUI() {
    const main = document.querySelector(".main");

    if (!main || document.getElementById("page-business")) {
        return;
    }

    const section = document.createElement("section");
    section.id = "page-business";
    section.className = "page hidden";
    section.innerHTML = `
        <div class="section-header">
            <div>
                <h2>Business Operations</h2>
                <p>Leads, bookings, orders and human handoffs</p>
            </div>
        </div>

        <div class="panel">
            <div class="form-group">
                <label>Company</label>
                <select id="business-company" onchange="businessCompanyChanged()"></select>
            </div>
        </div>

        <div class="cards" style="margin-top:20px">
            <div class="card"><div class="card-label">Leads</div><div id="business-leads-count" class="card-value">0</div></div>
            <div class="card"><div class="card-label">Bookings</div><div id="business-bookings-count" class="card-value">0</div></div>
            <div class="card"><div class="card-label">Orders</div><div id="business-orders-count" class="card-value">0</div></div>
            <div class="card"><div class="card-label">Human Handoffs</div><div id="business-handoffs-count" class="card-value">0</div></div>
        </div>

        <div id="business-content" style="margin-top:20px"></div>
    `;

    main.appendChild(section);
}


async function openBusinessPage(button) {
    document.querySelectorAll(".page")
        .forEach(x => x.classList.add("hidden"));

    document.querySelectorAll(".nav-item")
        .forEach(x => x.classList.remove("active"));

    document.getElementById("page-business")
        .classList.remove("hidden");

    if (button) {
        if (button) {
        button.classList.add("active");
    }
    }

    document.getElementById("page-title").textContent =
        "Business Operations";

    await loadBusinessCompanies();
    await businessCompanyChanged();
}


async function loadBusinessCompanies() {
    const result = await api("/admin/companies");
    const companies = result.companies || [];

    const select =
        document.getElementById("business-company");

    select.innerHTML = companies.map(company => `
        <option value="${company.id}">
            ${businessSafe(company.name)}
        </option>
    `).join("");

    if (companies.length) {

        const preferredCompanyId =
            sessionStorage.getItem(
                "xvondServiceCompanyId"
            );

        const exists =
            preferredCompanyId
            && companies.some(
                company =>
                    String(company.id)
                    === String(preferredCompanyId)
            );

        select.value =
            exists
            ? preferredCompanyId
            : companies[0].id;

        sessionStorage.removeItem(
            "xvondServiceCompanyId"
        );
    }
}


async function businessCompanyChanged() {
    const select =
        document.getElementById("business-company");

    if (!select || !select.value) return;

    businessCompanyId = Number(select.value);

    await loadBusinessOperations();
}


async function loadBusinessOperations() {
    try {
        const [leadsResult, bookingsResult, ordersResult, handoffsResult] =
            await Promise.all([
                api(`/admin/business/leads?company_id=${businessCompanyId}`),
                api(`/admin/business/bookings?company_id=${businessCompanyId}`),
                api(`/admin/business/orders?company_id=${businessCompanyId}`),
                api(`/admin/business/handoffs?company_id=${businessCompanyId}`)
            ]);

        const leads = Array.isArray(leadsResult) ? leadsResult : (leadsResult.leads || []);
        const bookings = Array.isArray(bookingsResult) ? bookingsResult : (bookingsResult.bookings || []);
        const orders = Array.isArray(ordersResult) ? ordersResult : (ordersResult.orders || []);
        const handoffs = Array.isArray(handoffsResult) ? handoffsResult : (handoffsResult.handoffs || []);

        document.getElementById("business-leads-count").textContent =
            leads.length;

        document.getElementById("business-bookings-count").textContent =
            bookings.length;

        document.getElementById("business-orders-count").textContent =
            orders.length;

        document.getElementById("business-handoffs-count").textContent =
            handoffs.length;

        document.getElementById("business-content").innerHTML = `
            ${businessSection("Leads", leads, "lead")}
            ${businessSection("Bookings", bookings, "booking")}
            ${businessSection("Orders", orders, "order")}
            ${businessSection("Human Handoffs", handoffs, "handoff")}
        `;

    } catch (error) {
        alert(error.message);
    }
}


function businessSection(title, items, type) {
    return `
        <div class="panel" style="margin-bottom:20px">

            <div class="section-header">
                <div>
                    <h3>${title}</h3>
                </div>
            </div>

            ${
                items.length
                ? items.map(item => businessItem(item, type)).join("")
                : `<p>No ${title.toLowerCase()} yet.</p>`
            }

        </div>
    `;
}


function businessItem(item, type) {
    const title =
        item.name ||
        item.customer_name ||
        item.title ||
        item.subject ||
        `${type} #${item.id}`;

    return `
        <div class="agent-card" style="margin-bottom:10px">

            <strong>
                ${businessSafe(title)}
            </strong>

            <div class="meta">
                ID: ${item.id}
            </div>

            <div class="meta">
                Agent: ${item.agent_id ?? "-"}
            </div>

            <div class="meta">
                Status: ${businessSafe(item.status || "-")}
            </div>

            ${
                item.phone
                ? `<div class="meta">Phone: ${businessSafe(item.phone)}</div>`
                : ""
            }

            ${
                item.email
                ? `<div class="meta">Email: ${businessSafe(item.email)}</div>`
                : ""
            }

            <div style="margin-top:10px">
                <button class="table-button"
                    onclick="changeBusinessStatus(
                        '${type}',
                        ${item.id},
                        'new'
                    )">
                    New
                </button>

                <button class="table-button"
                    onclick="changeBusinessStatus(
                        '${type}',
                        ${item.id},
                        'in_progress'
                    )">
                    In Progress
                </button>

                <button class="table-button"
                    onclick="changeBusinessStatus(
                        '${type}',
                        ${item.id},
                        'completed'
                    )">
                    Completed
                </button>
            </div>

        </div>
    `;
}


async function changeBusinessStatus(type, id, status) {
    try {
        await api(
            `/admin/business/${type}s/${id}/status/${status}`,
            {
                method: "PATCH"
            }
        );

        await loadBusinessOperations();

    } catch (error) {
        alert(error.message);
    }
}


function businessSafe(value) {
    const element = document.createElement("div");
    element.textContent = value ?? "";
    return element.innerHTML;
}


document.addEventListener(
    "DOMContentLoaded",
    installBusinessUI
);
