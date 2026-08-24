let pilotCompanyId = null;
let pilotConversationId = null;


function installPilotConsole() {

    const nav = document.querySelector(
        ".sidebar nav"
    );

    if (
        nav &&
        !document.getElementById(
            "pilot-console-nav"
        )
    ) {

        const button =
            document.createElement(
                "button"
            );

        button.id =
            "pilot-console-nav";

        button.className =
            "nav-item";

        button.innerText =
            "Pilot Console";

        button.onclick =
            () => openPilotConsole(
                button
            );

        nav.appendChild(
            button
        );
    }


    const main =
        document.querySelector(
            ".main"
        );

    if (
        main &&
        !document.getElementById(
            "page-pilot"
        )
    ) {

        const section =
            document.createElement(
                "section"
            );

        section.id =
            "page-pilot";

        section.className =
            "page hidden";

        section.innerHTML = `

            <div class="section-header">

                <div>

                    <h2>
                        AI Agent Pilot
                    </h2>

                    <p>
                        Build and test an AI service
                        for a customer company.
                    </p>

                </div>

            </div>


            <div class="panel">

                <div class="form-group">

                    <label>
                        Customer Company
                    </label>

                    <select
                        id="pilot-company-select"
                        onchange="loadPilotCompany()"
                    >
                    </select>

                </div>

            </div>


            <div
                id="pilot-content"
                style="margin-top:20px"
            >
            </div>
        `;

        main.appendChild(
            section
        );
    }
}


async function openPilotConsole(
    navButton
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
        "page-pilot"
    ).classList.remove(
        "hidden"
    );

    if (navButton) {
        navButton.classList.add(
            "active"
        );
    }

    document.getElementById(
        "page-title"
    ).innerText =
        "AI Agent Pilot";

    await loadPilotCompanies();
}


async function loadPilotCompanies() {

    try {

        const result =
            await api(
                "/admin/companies"
            );

        const companies =
            result.companies || [];

        const select =
            document.getElementById(
                "pilot-company-select"
            );

        select.innerHTML = `
            <option value="">
                Select company
            </option>
        `;

        for (const company of companies) {

            select.innerHTML += `
                <option value="${company.id}">
                    ${escapePilot(company.name)}
                </option>
            `;
        }

        if (companies.length > 0) {

            select.value =
                companies[0].id;

            await loadPilotCompany();
        }

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function loadPilotCompany() {

    const select =
        document.getElementById(
            "pilot-company-select"
        );

    if (!select.value) {
        return;
    }

    pilotCompanyId =
        Number(select.value);

    pilotConversationId =
        null;

    try {

        const company =
            await api(
                `/admin/company-view/${pilotCompanyId}`
            );

        let modules = [];

        try {

            const moduleResult =
                await api(
                    `/admin/companies/${pilotCompanyId}/modules`
                );

            modules =
                moduleResult.modules || [];

        } catch (_) {
        }


        const aiModule =
            modules.find(
                item =>
                    item.module_name === "ai_agent"
                    ||
                    item.name === "ai_agent"
            );


        const aiEnabled =
            aiModule
            ? aiModule.enabled !== false
            : false;


        const content =
            document.getElementById(
                "pilot-content"
            );


        content.innerHTML = `

            <div class="cards">

                <div class="card">

                    <div class="card-label">
                        Company
                    </div>

                    <div
                        class="card-value"
                        style="font-size:20px"
                    >
                        ${escapePilot(
                            company.company.name
                        )}
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        AI Agent Service
                    </div>

                    <div
                        class="card-value"
                        style="font-size:20px"
                    >
                        ${
                            aiEnabled
                            ? "Active"
                            : "Inactive"
                        }
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        Agents
                    </div>

                    <div class="card-value">
                        ${company.agents.length}
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        Conversations
                    </div>

                    <div class="card-value">
                        ${
                            company.analytics
                                .conversations
                        }
                    </div>

                </div>

            </div>


            <div
                class="panel"
                style="margin-top:20px"
            >

                <div class="section-header">

                    <div>

                        <h3>
                            Step 1 — AI Service
                        </h3>

                        <p>
                            Enable the AI Agent module
                            for this company.
                        </p>

                    </div>

                </div>


                ${
                    aiEnabled
                    ? `
                        <span
                            class="
                                status
                                status-active
                            "
                        >
                            AI Agent Module Active
                        </span>
                    `
                    : `
                        <button
                            class="primary-button"
                            onclick="
                                activatePilotAI()
                            "
                        >
                            Activate AI Agent Service
                        </button>
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
                            Step 2 — Agents
                        </h3>

                        <p>
                            Build an agent for
                            this customer.
                        </p>

                    </div>


                    <button
                        onclick="
                            openCreateAgent(
                                ${pilotCompanyId}
                            )
                        "
                        ${
                            aiEnabled
                            ? ""
                            : "disabled"
                        }
                    >
                        + Create Agent
                    </button>

                </div>


                <div class="agent-grid">

                    ${
                        company.agents.length
                        ?
                        company.agents.map(
                            agent => `

                            <div class="agent-card">

                                <h3>
                                    ${escapePilot(
                                        agent.name
                                    )}
                                </h3>

                                <div class="meta">
                                    Provider:
                                    ${escapePilot(
                                        agent.provider
                                    )}
                                </div>

                                <div class="meta">
                                    Model:
                                    ${escapePilot(
                                        agent.model
                                    )}
                                </div>

                                <div class="meta">
                                    Status:
                                    ${
                                        agent.enabled
                                        ? "Enabled"
                                        : "Disabled"
                                    }
                                </div>


                                <div
                                    style="
                                        display:flex;
                                        flex-wrap:wrap;
                                        gap:8px;
                                        margin-top:15px;
                                    "
                                >

                                    <button
                                        class="table-button"
                                        onclick="
                                            openPilotKnowledge(
                                                ${pilotCompanyId},
                                                ${agent.id}
                                            )
                                        "
                                    >
                                        Add Knowledge
                                    </button>


                                    <button
                                        class="table-button"
                                        onclick="
                                            openPilotChat(
                                                ${pilotCompanyId},
                                                ${agent.id},
                                                '${escapePilotJs(
                                                    agent.name
                                                )}'
                                            )
                                        "
                                    >
                                        Test Agent
                                    </button>

                                </div>

                            </div>

                            `
                        ).join("")
                        :
                        `
                            <p>
                                No AI agents yet.
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
                    Pilot Statistics
                </h3>

                <div class="meta">
                    AI Requests:
                    ${
                        company.analytics
                            .ai_requests
                    }
                </div>

                <div class="meta">
                    Tokens:
                    ${
                        company.analytics
                            .tokens
                    }
                </div>

                <div class="meta">
                    Provider Cost:
                    ${
                        company.analytics
                            .provider_cost
                    }
                </div>

            </div>
        `;

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function activatePilotAI() {

    try {

        try {

            await api(
                `/admin/companies/${pilotCompanyId}/modules/ai_agent`,
                {
                    method: "POST"
                }
            );

        } catch (_) {
        }


        try {

            await api(
                `/admin/companies/${pilotCompanyId}/modules/ai_agent/enable`,
                {
                    method: "POST"
                }
            );

        } catch (error) {

            alert(
                error.message
            );

            return;
        }


        await loadPilotCompany();

    } catch (error) {

        alert(
            error.message
        );
    }
}


function openPilotKnowledge(
    companyId,
    agentId
) {

    openModal(
        "Add Agent Knowledge",
        `

        <div class="form-group">

            <label>
                Knowledge Name
            </label>

            <input
                id="pilot-knowledge-title"
                placeholder="Services / Menu / FAQ / Prices"
            >

        </div>


        <div class="form-group">

            <label>
                Company Information
            </label>

            <textarea
                id="pilot-knowledge-content"
                style="min-height:250px"
                placeholder="Paste company information here..."
            ></textarea>

        </div>


        <button
            class="modal-submit"
            onclick="
                savePilotKnowledge(
                    ${companyId},
                    ${agentId}
                )
            "
        >
            Save Knowledge
        </button>
        `
    );
}


async function savePilotKnowledge(
    companyId,
    agentId
) {

    const title =
        document.getElementById(
            "pilot-knowledge-title"
        ).value.trim();

    const content =
        document.getElementById(
            "pilot-knowledge-content"
        ).value.trim();


    if (!title || !content) {

        alert(
            "Enter title and company information."
        );

        return;
    }


    try {

        const documentResult =
            await api(
                `/admin/knowledge/companies/${companyId}/documents`,
                {
                    method: "POST",

                    body: JSON.stringify({
                        title: title,
                        source_type: "text",
                        content: content
                    })
                }
            );


        await api(
            `/admin/knowledge/agents/${agentId}/documents/${documentResult.id}`,
            {
                method: "POST"
            }
        );


        closeModal();


        alert(
            "Knowledge connected to agent."
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}


function openPilotChat(
    companyId,
    agentId,
    agentName
) {

    pilotConversationId =
        null;


    openModal(
        `Test Agent — ${agentName}`,
        `

        <div
            id="pilot-chat"
            style="
                height:300px;
                overflow:auto;
                background:#f7f8fa;
                border:1px solid #e5e7eb;
                border-radius:10px;
                padding:12px;
                margin-bottom:15px;
            "
        >
            <div class="meta">
                Start testing the agent.
            </div>
        </div>


        <div class="form-group">

            <label>
                Message
            </label>

            <textarea
                id="pilot-message"
                placeholder="مرحبا، شو الخدمات يلي عندكم؟"
            ></textarea>

        </div>


        <button
            class="modal-submit"
            onclick="
                sendPilotMessage(
                    ${companyId},
                    ${agentId}
                )
            "
        >
            Send Message
        </button>
        `
    );
}


async function sendPilotMessage(
    companyId,
    agentId
) {

    const input =
        document.getElementById(
            "pilot-message"
        );

    const message =
        input.value.trim();


    if (!message) {
        return;
    }


    const chat =
        document.getElementById(
            "pilot-chat"
        );


    chat.innerHTML += `

        <div
            style="
                background:white;
                padding:10px;
                border-radius:8px;
                margin-bottom:10px;
            "
        >

            <strong>
                You
            </strong>

            <div>
                ${escapePilot(message)}
            </div>

        </div>
    `;


    input.value = "";


    try {

        const result =
            await api(
                `/admin/companies/${companyId}/agents/${agentId}/test-chat`,
                {
                    method: "POST",

                    body: JSON.stringify({
                        message: message,
                        conversation_id:
                            pilotConversationId
                    })
                }
            );


        pilotConversationId =
            result.conversation_id;


        chat.innerHTML += `

            <div
                style="
                    background:#eaf3ff;
                    padding:10px;
                    border-radius:8px;
                    margin-bottom:10px;
                "
            >

                <strong>
                    Agent
                </strong>

                <div>
                    ${escapePilot(
                        result.response.content
                    )}
                </div>

                <div
                    class="meta"
                    style="margin-top:8px"
                >
                    ${escapePilot(
                        result.provider
                    )}
                    /
                    ${escapePilot(
                        result.model
                    )}
                </div>

            </div>
        `;


        chat.scrollTop =
            chat.scrollHeight;


    } catch (error) {

        chat.innerHTML += `

            <div
                style="
                    color:#b42318;
                    margin-bottom:10px;
                "
            >
                ${escapePilot(
                    error.message
                )}
            </div>
        `;
    }
}


function escapePilot(
    value
) {

    const element =
        document.createElement(
            "div"
        );

    element.textContent =
        value ?? "";

    return element.innerHTML
        .replaceAll(
            "\n",
            "<br>"
        );
}


function escapePilotJs(
    value
) {

    return String(
        value ?? ""
    )
    .replaceAll(
        "\\",
        "\\\\"
    )
    .replaceAll(
        "'",
        "\\'"
    );
}


document.addEventListener(
    "DOMContentLoaded",
    installPilotConsole
);


setTimeout(
    installPilotConsole,
    300
);
