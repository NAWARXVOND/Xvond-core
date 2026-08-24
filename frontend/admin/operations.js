let opsCompanyId = null;


function installOperationsUI() {

    const nav =
        document.querySelector(
            ".sidebar nav"
        );

    const main =
        document.querySelector(
            ".main"
        );

    if (!nav || !main) {
        return;
    }


    const pages = [
        ["billing-service", "Billing"],
        ["usage-service", "Usage"],
        ["conversations-service", "Conversations"],
        ["audit-service", "Audit Logs"],
    ];


    for (const [id, title] of pages) {

        if (
            !document.getElementById(
                `nav-${id}`
            )
        ) {

            const button =
                document.createElement(
                    "button"
                );

            button.id =
                `nav-${id}`;

            button.className =
                "nav-item";

            button.textContent =
                title;

            button.onclick =
                () =>
                    openOperationsPage(
                        id,
                        title,
                        button
                    );

            nav.appendChild(
                button
            );
        }


        if (
            !document.getElementById(
                `page-${id}`
            )
        ) {

            const section =
                document.createElement(
                    "section"
                );

            section.id =
                `page-${id}`;

            section.className =
                "page hidden";

            section.innerHTML = `

                <div class="section-header">

                    <div>

                        <h2>
                            ${title}
                        </h2>

                    </div>

                </div>


                <div
                    id="${id}-company-box"
                    class="panel"
                >

                    <div class="form-group">

                        <label>
                            Company
                        </label>

                        <select
                            id="${id}-company"
                            onchange="
                                operationCompanyChanged(
                                    '${id}'
                                )
                            "
                        >
                        </select>

                    </div>

                </div>


                <div
                    id="${id}-content"
                    style="margin-top:20px"
                >
                </div>
            `;


            main.appendChild(
                section
            );
        }
    }
}


async function openOperationsPage(
    id,
    title,
    button
) {

    document
        .querySelectorAll(
            ".page"
        )
        .forEach(
            item =>
                item.classList.add(
                    "hidden"
                )
        );


    document
        .querySelectorAll(
            ".nav-item"
        )
        .forEach(
            item =>
                item.classList.remove(
                    "active"
                )
        );


    document.getElementById(
        `page-${id}`
    ).classList.remove(
        "hidden"
    );


    button.classList.add(
        "active"
    );


    document.getElementById(
        "page-title"
    ).textContent =
        title;


    if (
        id === "audit-service"
    ) {

        document.getElementById(
            "audit-service-company-box"
        ).style.display =
            "none";


        await loadAuditPage();

        return;
    }


    await loadOperationCompanies(
        id
    );


    await operationCompanyChanged(
        id
    );
}


async function loadOperationCompanies(
    id
) {

    const result =
        await api(
            "/admin/companies"
        );


    const companies =
        result.companies || [];


    const select =
        document.getElementById(
            `${id}-company`
        );


    select.innerHTML =
        companies.map(
            company => `

            <option value="${company.id}">
                ${safeOps(
                    company.name
                )}
            </option>

            `
        ).join("");


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


async function operationCompanyChanged(
    id
) {

    const select =
        document.getElementById(
            `${id}-company`
        );


    if (
        !select
        || !select.value
    ) {
        return;
    }


    opsCompanyId =
        Number(
            select.value
        );


    if (
        id === "billing-service"
    ) {
        await loadBillingPage();
    }


    if (
        id === "usage-service"
    ) {
        await loadUsagePage();
    }


    if (
        id === "conversations-service"
    ) {
        await loadConversationsPage();
    }
}


async function loadBillingPage() {

    try {

        const plansResult =
            await api(
                "/admin/billing/plans"
            );


        const subscriptionsResult =
            await api(
                "/admin/operations/subscriptions"
            );


        const company =
            await api(
                `/admin/company-view/${opsCompanyId}`
            );


        const plans =
            plansResult.plans || [];


        const subscriptions =
            subscriptionsResult
                .subscriptions || [];


        const content =
            document.getElementById(
                "billing-service-content"
            );


        content.innerHTML = `

            <div class="panel">

                <div class="section-header">

                    <div>

                        <h3>
                            Company Subscription
                        </h3>

                    </div>

                    <button
                        onclick="
                            openAssignPlan()
                        "
                    >
                        Assign Plan
                    </button>

                </div>


                ${
                    company.subscription
                    ?
                    `

                    <div class="agent-card">

                        <h3>
                            ${
                                safeOps(
                                    company.subscription
                                    .plan?.name
                                    || "Plan"
                                )
                            }
                        </h3>

                        <div class="meta">

                            Status:
                            ${safeOps(
                                company.subscription
                                    .status
                            )}

                        </div>

                        <div class="meta">

                            Price:
                            ${
                                company.subscription
                                .plan?.price
                                ?? 0
                            }

                        </div>

                    </div>

                    `
                    :
                    `

                    <p>
                        No active subscription
                        for this company.
                    </p>

                    `
                }

            </div>


            <div
                class="panel"
                style="margin-top:20px"
            >

                <div class="section-header">

                    <div>

                        <h3>
                            Plans
                        </h3>

                    </div>

                    <button
                        onclick="
                            openCreatePlan()
                        "
                    >
                        + Create Plan
                    </button>

                </div>


                <div class="agent-grid">

                    ${
                        plans.length
                        ?
                        plans.map(
                            plan => `

                            <div class="agent-card">

                                <h3>
                                    ${safeOps(
                                        plan.name
                                    )}
                                </h3>

                                <div class="meta">
                                    Price:
                                    ${plan.price}
                                </div>

                                <div class="meta">
                                    Agents:
                                    ${plan.agent_limit}
                                </div>

                                <div class="meta">
                                    Tokens:
                                    ${plan.token_limit}
                                </div>

                                <div class="meta">
                                    Channels:
                                    ${plan.channel_limit}
                                </div>

                            </div>

                            `
                        ).join("")
                        :
                        `
                            <p>
                                No plans yet.
                            </p>
                        `
                    }

                </div>

            </div>


            <div
                class="panel"
                style="margin-top:20px"
            >

                <h3>
                    All Subscriptions
                </h3>

                ${
                    subscriptions.length
                    ?
                    subscriptions.map(
                        item => `

                        <div class="agent-card">

                            <strong>
                                ${safeOps(
                                    item.company_name
                                )}
                            </strong>

                            <div class="meta">
                                ${safeOps(
                                    item.plan_name
                                )}
                                —
                                ${safeOps(
                                    item.status
                                )}
                            </div>

                        </div>

                        `
                    ).join("")
                    :
                    `
                        <p>
                            No subscriptions.
                        </p>
                    `
                }

            </div>
        `;

    } catch (error) {

        alert(
            error.message
        );
    }
}


function openCreatePlan() {

    openModal(
        "Create Billing Plan",
        `

        <div class="form-group">
            <label>Name</label>
            <input id="ops-plan-name">
        </div>

        <div class="form-group">
            <label>Price</label>
            <input
                id="ops-plan-price"
                type="number"
                step="0.001"
                value="0"
            >
        </div>

        <div class="form-group">
            <label>Agent Limit</label>
            <input
                id="ops-agent-limit"
                type="number"
                value="1"
            >
        </div>

        <div class="form-group">
            <label>Token Limit</label>
            <input
                id="ops-token-limit"
                type="number"
                value="0"
            >
        </div>

        <div class="form-group">
            <label>Channel Limit</label>
            <input
                id="ops-channel-limit"
                type="number"
                value="0"
            >
        </div>

        <button
            class="modal-submit"
            onclick="
                createOpsPlan()
            "
        >
            Create Plan
        </button>
        `
    );
}


async function createOpsPlan() {

    try {

        await api(
            "/admin/billing/plans",
            {
                method: "POST",

                body: JSON.stringify({

                    name:
                        document.getElementById(
                            "ops-plan-name"
                        ).value,

                    price:
                        Number(
                            document.getElementById(
                                "ops-plan-price"
                            ).value
                        ),

                    agent_limit:
                        Number(
                            document.getElementById(
                                "ops-agent-limit"
                            ).value
                        ),

                    token_limit:
                        Number(
                            document.getElementById(
                                "ops-token-limit"
                            ).value
                        ),

                    channel_limit:
                        Number(
                            document.getElementById(
                                "ops-channel-limit"
                            ).value
                        )
                })
            }
        );


        closeModal();

        await loadBillingPage();

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function openAssignPlan() {

    try {

        const result =
            await api(
                "/admin/billing/plans"
            );


        const plans =
            result.plans || [];


        if (!plans.length) {

            alert(
                "Create a billing plan first."
            );

            return;
        }


        openModal(
            "Assign Plan",
            `

            <div class="form-group">

                <label>
                    Plan
                </label>

                <select
                    id="ops-plan-select"
                >

                    ${
                        plans.map(
                            plan => `

                            <option
                                value="${plan.id}"
                            >
                                ${safeOps(
                                    plan.name
                                )}
                            </option>

                            `
                        ).join("")
                    }

                </select>

            </div>


            <button
                class="modal-submit"
                onclick="
                    assignOpsPlan()
                "
            >
                Assign
            </button>

            `
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function assignOpsPlan() {

    try {

        const planId =
            Number(
                document.getElementById(
                    "ops-plan-select"
                ).value
            );


        await api(
            `/admin/billing/companies/${opsCompanyId}/subscription`,
            {
                method: "POST",

                body: JSON.stringify({
                    plan_id: planId
                })
            }
        );


        closeModal();

        await loadBillingPage();

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function loadUsagePage() {

    try {

        const result =
            await api(
                `/admin/operations/companies/${opsCompanyId}/usage`
            );


        const summary =
            result.summary;


        const items =
            result.usage || [];


        document.getElementById(
            "usage-service-content"
        ).innerHTML = `

            <div class="cards">

                <div class="card">

                    <div class="card-label">
                        Requests
                    </div>

                    <div class="card-value">
                        ${summary.requests}
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        Input Tokens
                    </div>

                    <div class="card-value">
                        ${summary.input_tokens}
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        Output Tokens
                    </div>

                    <div class="card-value">
                        ${summary.output_tokens}
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        Total Tokens
                    </div>

                    <div class="card-value">
                        ${summary.total_tokens}
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        Provider Cost
                    </div>

                    <div class="card-value">
                        ${summary.provider_cost}
                    </div>

                </div>

            </div>


            <div
                class="panel"
                style="margin-top:20px"
            >

                <h3>
                    Usage History
                </h3>


                ${
                    items.length
                    ?
                    items.map(
                        item => `

                        <div class="agent-card">

                            <strong>
                                Request #${item.id}
                            </strong>

                            <div class="meta">

                                Agent:
                                ${item.agent_id}

                            </div>

                            <div class="meta">

                                ${safeOps(
                                    item.provider
                                )}
                                /
                                ${safeOps(
                                    item.model
                                )}

                            </div>

                            <div class="meta">

                                Tokens:
                                ${item.total_tokens}

                            </div>

                            <div class="meta">

                                Cost:
                                ${item.provider_cost}

                            </div>

                        </div>

                        `
                    ).join("")
                    :
                    `
                        <p>
                            No usage recorded.
                        </p>
                    `
                }

            </div>
        `;

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function loadConversationsPage() {

    try {

        const result =
            await api(
                `/admin/operations/companies/${opsCompanyId}/conversations`
            );


        const items =
            result.conversations || [];


        document.getElementById(
            "conversations-service-content"
        ).innerHTML = `

            <div class="panel">

                <h3>
                    Conversations
                </h3>


                ${
                    items.length
                    ?
                    items.map(
                        item => `

                        <div
                            class="agent-card"
                            style="margin-bottom:10px"
                        >

                            <strong>
                                ${safeOps(
                                    item.title
                                    || "Conversation"
                                )}
                            </strong>

                            <div class="meta">
                                Agent:
                                ${item.agent_id}
                            </div>

                            <div class="meta">
                                ID:
                                ${item.id}
                            </div>

                            <button
                                class="table-button"
                                onclick="
                                    openOpsConversation(
                                        ${item.id}
                                    )
                                "
                            >
                                Open Conversation
                            </button>

                        </div>

                        `
                    ).join("")
                    :
                    `
                        <p>
                            No conversations yet.
                        </p>
                    `
                }

            </div>
        `;

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function openOpsConversation(
    conversationId
) {

    try {

        const result =
            await api(
                `/admin/operations/companies/${opsCompanyId}/conversations/${conversationId}`
            );


        const messages =
            result.messages || [];


        openModal(
            "Conversation",
            `

            <div
                style="
                    max-height:500px;
                    overflow:auto;
                "
            >

                ${
                    messages.map(
                        message => `

                        <div
                            class="agent-card"
                            style="margin-bottom:10px"
                        >

                            <strong>
                                ${safeOps(
                                    message.role
                                )}
                            </strong>

                            <p
                                style="
                                    white-space:pre-wrap;
                                "
                            >
                                ${safeOps(
                                    message.content
                                )}
                            </p>

                        </div>

                        `
                    ).join("")
                }

            </div>
            `
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function loadAuditPage() {

    try {

        const result =
            await api(
                "/admin/audit/"
            );


        const logs =
            result.logs || [];


        document.getElementById(
            "audit-service-content"
        ).innerHTML = `

            <div class="panel">

                <h3>
                    Audit Logs
                </h3>


                ${
                    logs.length
                    ?
                    logs.map(
                        item => `

                        <div
                            class="agent-card"
                            style="margin-bottom:10px"
                        >

                            <strong>
                                ${safeOps(
                                    item.action
                                )}
                            </strong>

                            <div class="meta">

                                Company:
                                ${
                                    item.company_id
                                    ?? "-"
                                }

                            </div>

                            <div class="meta">

                                User:
                                ${
                                    item.user_id
                                    ?? "-"
                                }

                            </div>

                            <div class="meta">

                                Resource:
                                ${safeOps(
                                    item.resource_type
                                    || "-"
                                )}

                                ${
                                    item.resource_id
                                    ?? ""
                                }

                            </div>

                            <div class="meta">

                                ${
                                    safeOps(
                                        JSON.stringify(
                                            item.details
                                            || {}
                                        )
                                    )
                                }

                            </div>

                        </div>

                        `
                    ).join("")
                    :
                    `
                        <p>
                            No audit logs yet.
                        </p>
                    `
                }

            </div>
        `;

    } catch (error) {

        alert(
            error.message
        );
    }
}


function safeOps(
    value
) {

    const element =
        document.createElement(
            "div"
        );

    element.textContent =
        value ?? "";

    return element.innerHTML;
}


document.addEventListener(
    "DOMContentLoaded",
    installOperationsUI
);


setTimeout(
    installOperationsUI,
    600
);

