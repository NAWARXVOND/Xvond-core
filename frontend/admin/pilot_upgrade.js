let xvondPilotBaseLoadCompany =
    window.loadPilotCompany;


window.loadPilotCompany =
async function() {

    await xvondPilotBaseLoadCompany();

    await renderPilotManagement();
};


async function renderPilotManagement() {

    if (!pilotCompanyId) {
        return;
    }

    try {

        const company =
            await api(
                `/admin/company-view/${pilotCompanyId}`
            );

        const content =
            document.getElementById(
                "pilot-content"
            );

        if (!content) {
            return;
        }

        const old =
            document.getElementById(
                "pilot-management"
            );

        if (old) {
            old.remove();
        }


        const panel =
            document.createElement(
                "div"
            );

        panel.id =
            "pilot-management";

        panel.className =
            "panel";

        panel.style.marginTop =
            "20px";


        panel.innerHTML = `

            <div class="section-header">

                <div>

                    <h3>
                        Agent Management
                    </h3>

                    <p>
                        Control agents, knowledge
                        and current usage.
                    </p>

                </div>

            </div>


            <div class="cards">

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


                <div class="card">

                    <div class="card-label">
                        AI Requests
                    </div>

                    <div class="card-value">
                        ${
                            company.analytics
                                .ai_requests
                        }
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        Tokens
                    </div>

                    <div class="card-value">
                        ${
                            company.analytics
                                .tokens
                        }
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        Provider Cost
                    </div>

                    <div class="card-value">
                        ${
                            company.analytics
                                .provider_cost
                        }
                    </div>

                </div>

            </div>


            <div
                class="agent-grid"
                style="margin-top:20px"
            >

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
                                ${escapePilot(
                                    agent.provider
                                )}
                                /
                                ${escapePilot(
                                    agent.model
                                )}
                            </div>


                            <div class="meta">

                                Status:

                                <strong>
                                    ${
                                        agent.enabled
                                        ? "Enabled"
                                        : "Disabled"
                                    }
                                </strong>

                            </div>


                            <div
                                style="
                                    display:flex;
                                    gap:8px;
                                    flex-wrap:wrap;
                                    margin-top:15px;
                                "
                            >

                                ${
                                    agent.enabled
                                    ?
                                    `
                                    <button
                                        class="table-button"
                                        onclick="
                                            setPilotAgentStatus(
                                                ${pilotCompanyId},
                                                ${agent.id},
                                                false
                                            )
                                        "
                                    >
                                        Disable
                                    </button>
                                    `
                                    :
                                    `
                                    <button
                                        class="table-button"
                                        onclick="
                                            setPilotAgentStatus(
                                                ${pilotCompanyId},
                                                ${agent.id},
                                                true
                                            )
                                        "
                                    >
                                        Enable
                                    </button>
                                    `
                                }


                                <button
                                    class="table-button"
                                    onclick="
                                        manageAgentKnowledge(
                                            ${pilotCompanyId},
                                            ${agent.id},
                                            '${escapePilotJs(
                                                agent.name
                                            )}'
                                        )
                                    "
                                >
                                    Manage Knowledge
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
                                    Test
                                </button>

                            </div>

                        </div>

                        `
                    ).join("")
                    :
                    `
                        <p>
                            No agents yet.
                        </p>
                    `
                }

            </div>
        `;


        content.appendChild(
            panel
        );

    } catch (error) {

        console.error(
            error
        );
    }
}


async function setPilotAgentStatus(
    companyId,
    agentId,
    enabled
) {

    try {

        const action =
            enabled
            ? "enable"
            : "disable";


        await api(
            `/admin/companies/${companyId}/agents/${agentId}/${action}`,
            {
                method: "POST"
            }
        );


        await loadPilotCompany();

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function manageAgentKnowledge(
    companyId,
    agentId,
    agentName
) {

    try {

        const result =
            await api(
                `/admin/knowledge/agents/${agentId}/documents`
            );


        const documents =
            result.documents || [];


        openModal(
            `Knowledge — ${agentName}`,
            `

            <div
                style="
                    margin-bottom:15px;
                "
            >

                <button
                    class="primary-button"
                    onclick="
                        openPilotKnowledge(
                            ${companyId},
                            ${agentId}
                        )
                    "
                >
                    + Add Knowledge
                </button>

            </div>


            <div
                id="knowledge-manager-list"
            >

                ${
                    documents.length
                    ?
                    documents.map(
                        document => `

                        <div
                            class="agent-card"
                            style="
                                margin-bottom:12px;
                            "
                        >

                            <h3>
                                ${escapePilot(
                                    document.title
                                )}
                            </h3>


                            <p
                                style="
                                    white-space:pre-wrap;
                                "
                            >
                                ${escapePilot(
                                    document.content
                                )}
                            </p>


                            <div
                                style="
                                    display:flex;
                                    flex-wrap:wrap;
                                    gap:8px;
                                "
                            >

                                <button
                                    class="table-button"
                                    onclick="
                                        editPilotKnowledge(
                                            ${companyId},
                                            ${agentId},
                                            ${document.id}
                                        )
                                    "
                                >
                                    Edit
                                </button>


                                <button
                                    class="table-button"
                                    onclick="
                                        disconnectPilotKnowledge(
                                            ${companyId},
                                            ${agentId},
                                            ${document.id},
                                            '${escapePilotJs(
                                                agentName
                                            )}'
                                        )
                                    "
                                >
                                    Disconnect
                                </button>


                                <button
                                    class="table-button"
                                    onclick="
                                        deletePilotKnowledge(
                                            ${companyId},
                                            ${agentId},
                                            ${document.id},
                                            '${escapePilotJs(
                                                agentName
                                            )}'
                                        )
                                    "
                                >
                                    Delete
                                </button>

                            </div>

                        </div>

                        `
                    ).join("")
                    :
                    `
                        <p>
                            No knowledge connected
                            to this agent.
                        </p>
                    `
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


async function editPilotKnowledge(
    companyId,
    agentId,
    documentId
) {

    try {

        const document =
            await api(
                `/admin/knowledge/companies/${companyId}/documents/${documentId}`
            );


        openModal(
            "Edit Knowledge",
            `

            <div class="form-group">

                <label>
                    Title
                </label>

                <input
                    id="edit-knowledge-title"
                    value="${escapePilotAttribute(
                        document.title
                    )}"
                >

            </div>


            <div class="form-group">

                <label>
                    Content
                </label>

                <textarea
                    id="edit-knowledge-content"
                    style="min-height:250px"
                >${escapePilotTextarea(
                    document.content
                )}</textarea>

            </div>


            <button
                class="modal-submit"
                onclick="
                    saveEditedPilotKnowledge(
                        ${companyId},
                        ${agentId},
                        ${documentId}
                    )
                "
            >
                Save Changes
            </button>

            `
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function saveEditedPilotKnowledge(
    companyId,
    agentId,
    documentId
) {

    try {

        const title =
            document.getElementById(
                "edit-knowledge-title"
            ).value.trim();


        const content =
            document.getElementById(
                "edit-knowledge-content"
            ).value.trim();


        await api(
            `/admin/knowledge/companies/${companyId}/documents/${documentId}`,
            {
                method: "PATCH",

                body: JSON.stringify({
                    title: title,
                    content: content
                })
            }
        );


        closeModal();


        await manageAgentKnowledge(
            companyId,
            agentId,
            "Agent"
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function disconnectPilotKnowledge(
    companyId,
    agentId,
    documentId,
    agentName
) {

    if (
        !confirm(
            "Disconnect this knowledge from the agent?"
        )
    ) {
        return;
    }


    try {

        await api(
            `/admin/knowledge/agents/${agentId}/documents/${documentId}`,
            {
                method: "DELETE"
            }
        );


        await manageAgentKnowledge(
            companyId,
            agentId,
            agentName
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}


async function deletePilotKnowledge(
    companyId,
    agentId,
    documentId,
    agentName
) {

    if (
        !confirm(
            "Delete this knowledge permanently?"
        )
    ) {
        return;
    }


    try {

        await api(
            `/admin/knowledge/companies/${companyId}/documents/${documentId}`,
            {
                method: "DELETE"
            }
        );


        await manageAgentKnowledge(
            companyId,
            agentId,
            agentName
        );

    } catch (error) {

        alert(
            error.message
        );
    }
}


function escapePilotAttribute(
    value
) {

    return String(
        value ?? ""
    )
    .replaceAll(
        "&",
        "&amp;"
    )
    .replaceAll(
        '"',
        "&quot;"
    )
    .replaceAll(
        "<",
        "&lt;"
    )
    .replaceAll(
        ">",
        "&gt;"
    );
}


function escapePilotTextarea(
    value
) {

    return String(
        value ?? ""
    )
    .replaceAll(
        "&",
        "&amp;"
    )
    .replaceAll(
        "<",
        "&lt;"
    )
    .replaceAll(
        ">",
        "&gt;"
    );
}
