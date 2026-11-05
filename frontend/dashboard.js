        const API_BASE_URL = "";
        const apiUrl = path => `${API_BASE_URL || window.location.origin}${path}`;
        const state = {
            tickets: [],
            analytics: null,
            activePage: "overview",
            activeStatus: "all",
            search: "",
            selectedId: null,
            workflowByTicket: new Map(),
            lastWorkflow: null,
            toastTimer: null
        };

        const presets = [
            { name: "Delayed delivery", customer: "Alex Rivera", order: "ORD-1001", complaint: "Where is my order? It was supposed to arrive yesterday." },
            { name: "Shoe return", customer: "Priya Sharma", order: "ORD-2002", complaint: "I want to return the shoes I bought last week. How do I get a refund?" },
            { name: "Password reset", customer: "Sam Jenkins", order: "", complaint: "I forgot my password and can't log in." },
            { name: "Broken blender", customer: "Jordan Lee", order: "ORD-4004", complaint: "The blender I received is broken. Can I get a replacement?" },
            { name: "Multiple charges", customer: "Marcus Vance", order: "ORD-5005", complaint: "You charged my card three times! Fix this now or I'm contacting my bank and a lawyer." },
            { name: "Corporate gift cards", customer: "Elena Rostova", order: "", complaint: "Do you sell gift cards for a company of 500 employees with custom branding?" },
            { name: "Promo code", customer: "David Chen", order: "ORD-7007", complaint: "My promotional code SUMMER25 gives an invalid promo code error during checkout." },
            { name: "Account security", customer: "Sarah Connor", order: "ORD-8008", complaint: "Someone hacked into my account from a strange location and ordered items using my saved card!" }
        ];

        const knowledgeDocuments = [
            ["shipping_policy.md", "Shipping", "Delivery estimates, tracking, and delayed packages."],
            ["refund_policy.md", "Refund", "Return eligibility, packaging, labels, and refund timing."],
            ["account_and_login.md", "Account", "Password reset, verification, and account access."],
            ["product_faq.md", "Product", "Product replacements, promotions, and gift cards."],
            ["billing_and_payments.md", "Billing", "Duplicate charges, payments, and security concerns."]
        ];

        const agentDefinitions = [
            { name: "Customer Query Agent", role: "Classification and triage", description: "Identifies the complaint category, urgency, sentiment, summary, and escalation flags.", color: "#526dff", tint: "#edf0ff" },
            { name: "Knowledge Base Agent", role: "Policy retrieval", description: "Searches the local policy library and returns relevant passages with source filenames.", color: "#209a80", tint: "#e8f8f3" },
            { name: "Resolution Agent", role: "Grounded response", description: "Drafts a customer response from available policy context and assigns a confidence score.", color: "#a276d9", tint: "#f4edff" },
            { name: "Log Agent", role: "Escalation and audit", description: "Applies escalation rules and records the completed ticket in the CSV audit log.", color: "#d99027", tint: "#fff6e6" }
        ];

        const pageTitles = {
            overview: "Overview",
            tickets: "Tickets",
            agents: "AI Agents",
            knowledge: "Knowledge Base",
            analytics: "Analytics"
        };

        const byId = id => document.getElementById(id);
        const setText = (id, value) => { byId(id).textContent = value == null ? "" : String(value); };

        async function apiRequest(path, options = {}) {
            const response = await fetch(apiUrl(path), options);
            let data = null;
            const contentType = response.headers.get("content-type") || "";
            if (contentType.includes("application/json")) {
                data = await response.json();
            } else if (!response.ok) {
                data = { detail: await response.text() };
            }
            if (!response.ok) {
                const detail = data && data.detail;
                const message = Array.isArray(detail)
                    ? detail.map(item => item.msg || JSON.stringify(item)).join("; ")
                    : detail || `Request failed (${response.status})`;
                throw new Error(message);
            }
            return data;
        }

        function showToast(message, kind = "success") {
            const toast = byId("toast");
            toast.textContent = message;
            toast.className = `toast visible ${kind}`;
            clearTimeout(state.toastTimer);
            state.toastTimer = setTimeout(() => { toast.className = "toast"; }, 3600);
        }

        function setConnection(connected) {
            byId("connectionState").classList.toggle("offline", !connected);
            setText("connectionLabel", connected ? "API connected" : "API unavailable");
        }

        function normalizeTicket(record) {
            const complaint = record.complaint || "";
            const confidenceValue = record.confidence;
            const confidence = confidenceValue !== "" && confidenceValue != null && Number.isFinite(Number(confidenceValue))
                ? Number(confidenceValue)
                : null;
            return {
                ...record,
                ticket_id: record.ticket_id || "Unknown",
                complaint,
                title: complaint.length > 78 ? `${complaint.slice(0, 75)}…` : complaint || "Support request",
                customer_name: record.customer_name || "Guest",
                category: record.category || "General",
                status: record.status === "Escalated" ? "Escalated" : "Resolved",
                urgency: record.urgency || "Low",
                kb_sources: record.kb_sources || "None",
                confidence
            };
        }

        async function refreshDashboard(showMessage = false) {
            const refreshButton = byId("refreshButton");
            refreshButton.disabled = true;
            try {
                const [ticketData, analytics] = await Promise.all([
                    apiRequest("/api/tickets"),
                    apiRequest("/api/analytics")
                ]);
                state.tickets = (Array.isArray(ticketData.tickets) ? ticketData.tickets : []).map(normalizeTicket);
                state.analytics = analytics;
                if (!state.tickets.some(ticket => ticket.ticket_id === state.selectedId)) {
                    state.selectedId = state.tickets[0]?.ticket_id || null;
                }
                setConnection(true);
                setText("lastUpdated", `Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
                renderAll();
                if (showMessage) showToast("Dashboard data refreshed.");
            } catch (error) {
                setConnection(false);
                showToast(`Could not load support data: ${error.message}`, "error");
            } finally {
                refreshButton.disabled = false;
            }
        }

        function setPage(page) {
            if (!pageTitles[page]) return;
            state.activePage = page;
            document.querySelectorAll(".page").forEach(section => {
                section.classList.toggle("active", section.id === `page-${page}`);
            });
            document.querySelectorAll(".nav-link[data-page]").forEach(button => {
                const active = button.dataset.page === page;
                button.classList.toggle("active", active);
                button.setAttribute("aria-current", active ? "page" : "false");
            });
            setText("currentPageTitle", pageTitles[page]);
            document.title = `${pageTitles[page]} | ClothesSpot Support Desk`;
            document.querySelector(".sidebar").classList.remove("mobile-open");
            if (page === "tickets") renderTickets();
            if (page === "agents") renderAgents();
            if (page === "analytics") renderAnalytics();
        }

        function renderAll() {
            setText("navTicketCount", state.tickets.length);
            renderOverview();
            renderTickets();
            renderAgents();
            renderKnowledgeCards();
            renderAnalytics();
        }

        function renderOverview() {
            const data = state.analytics;
            if (!data) return;
            setText("metricTotal", data.total_tickets);
            setText("metricResolved", data.resolved_count);
            setText("metricEscalated", data.escalated_count);
            setText("metricEscalationRate", `${Number(data.escalation_rate || 0).toFixed(1)}%`);
            renderOutcomeChart();
            renderWorkflowCards(byId("overviewWorkflow"), false);
            renderRows(byId("recentTicketsBody"), state.tickets.slice().reverse().slice(0, 5), 5, true);
        }

        function renderOutcomeChart() {
            const container = byId("overviewChart");
            container.replaceChildren();
            const resolved = Number(state.analytics?.resolved_count || 0);
            const escalated = Number(state.analytics?.escalated_count || 0);
            const total = resolved + escalated;
            if (!total) {
                const empty = document.createElement("div");
                empty.className = "chart-empty";
                empty.textContent = "Ticket outcomes will appear here after the first complaint is processed.";
                container.appendChild(empty);
                return;
            }
            const width = 460, height = 190, pad = 28;
            const max = Math.max(resolved, escalated, 1);
            const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
            svg.setAttribute("role", "img");
            svg.setAttribute("aria-label", `${resolved} resolved and ${escalated} escalated tickets`);
            svg.setAttribute("width", "100%");
            svg.setAttribute("height", "190");
            [0, 1, 2, 3].forEach(index => {
                const y = pad + index * 42;
                const line = document.createElementNS(svg.namespaceURI, "line");
                line.setAttribute("x1", "98"); line.setAttribute("x2", "445");
                line.setAttribute("y1", String(y + 17)); line.setAttribute("y2", String(y + 17));
                line.setAttribute("stroke", "#edf1f7"); line.setAttribute("stroke-dasharray", "3 5");
                svg.appendChild(line);
            });
            [
                ["Resolved", resolved, "#20c997"],
                ["Escalated", escalated, "#e57580"]
            ].forEach(([label, count, color], index) => {
                const y = 40 + index * 76;
                const title = document.createElementNS(svg.namespaceURI, "text");
                title.setAttribute("x", "0"); title.setAttribute("y", String(y + 5));
                title.setAttribute("fill", "#65738a"); title.setAttribute("font-size", "11");
                title.textContent = label;
                svg.appendChild(title);
                const bar = document.createElementNS(svg.namespaceURI, "rect");
                bar.setAttribute("x", "98"); bar.setAttribute("y", String(y - 12));
                bar.setAttribute("width", String(Math.max(count ? 5 : 0, (count / max) * 295)));
                bar.setAttribute("height", "25"); bar.setAttribute("rx", "8");
                bar.setAttribute("fill", color);
                svg.appendChild(bar);
                const value = document.createElementNS(svg.namespaceURI, "text");
                value.setAttribute("x", String(108 + Math.max(0, (count / max) * 295)));
                value.setAttribute("y", String(y + 5)); value.setAttribute("fill", "#34435c");
                value.setAttribute("font-size", "11"); value.setAttribute("font-weight", "700");
                value.textContent = String(count);
                svg.appendChild(value);
            });
            container.appendChild(svg);
        }

        function renderWorkflowCards(container, expanded) {
            container.replaceChildren();
            agentDefinitions.forEach((agent, index) => {
                const card = document.createElement("article");
                card.className = `workflow-card${expanded ? " workflow-line" : ""}`;
                const top = document.createElement("div");
                top.className = "workflow-top";
                const number = document.createElement("span");
                number.className = "workflow-number";
                number.textContent = String(index + 1).padStart(2, "0");
                const title = document.createElement("span");
                title.className = "workflow-title";
                title.textContent = agent.name;
                top.append(number, title);
                const copy = document.createElement("p");
                copy.className = "workflow-copy";
                copy.textContent = agent.description;
                card.append(top, copy);
                container.appendChild(card);
            });
        }

        function statusClass(status) {
            return status === "Escalated" ? "status-escalated" : "status-resolved";
        }

        function priorityClass(urgency) {
            const normalized = String(urgency || "Low").toLowerCase();
            return normalized === "high" ? "priority-high" : normalized === "medium" ? "priority-medium" : "priority-low";
        }

        function makePill(text, className) {
            const pill = document.createElement("span");
            pill.className = className;
            pill.textContent = text;
            return pill;
        }

        function renderRows(tbody, tickets, columns, compact) {
            tbody.replaceChildren();
            if (!tickets.length) {
                const row = document.createElement("tr");
                const cell = document.createElement("td");
                cell.className = "empty-row";
                cell.colSpan = columns;
                cell.textContent = state.tickets.length ? "No tickets match your filters." : "No tickets yet. Create a ticket to begin.";
                row.appendChild(cell);
                tbody.appendChild(row);
                return;
            }
            tickets.forEach(ticket => {
                const row = document.createElement("tr");
                row.dataset.ticketId = ticket.ticket_id;
                if (ticket.ticket_id === state.selectedId) row.classList.add("selected");
                row.addEventListener("click", () => {
                    state.selectedId = ticket.ticket_id;
                    if (compact) setPage("tickets");
                    renderTickets();
                    renderOverview();
                });
                const id = document.createElement("td");
                id.className = "ticket-id";
                id.textContent = ticket.ticket_id;
                const complaint = document.createElement("td");
                complaint.className = "ticket-title";
                complaint.textContent = ticket.title;
                if (compact) {
                    const ticketCell = document.createElement("td");
                    const ticketLabel = document.createElement("div");
                    ticketLabel.className = "ticket-id";
                    ticketLabel.textContent = ticket.ticket_id;
                    ticketCell.append(ticketLabel, complaint);
                    const customer = document.createElement("td");
                    customer.className = "ticket-customer";
                    customer.textContent = ticket.customer_name;
                    const category = document.createElement("td");
                    category.textContent = ticket.category;
                    const priority = document.createElement("td");
                    priority.appendChild(makePill(ticket.urgency, `priority-pill ${priorityClass(ticket.urgency)}`));
                    const status = document.createElement("td");
                    status.appendChild(makePill(ticket.status, `status-pill ${statusClass(ticket.status)}`));
                    row.append(ticketCell, customer, category, priority, status);
                } else {
                    const category = document.createElement("td");
                    category.textContent = ticket.category;
                    const priority = document.createElement("td");
                    priority.appendChild(makePill(ticket.urgency, `priority-pill ${priorityClass(ticket.urgency)}`));
                    const status = document.createElement("td");
                    status.appendChild(makePill(ticket.status, `status-pill ${statusClass(ticket.status)}`));
                    if (columns === 5) row.append(id, complaint, category, priority, status);
                    else {
                        const customer = document.createElement("td");
                        customer.className = "ticket-customer";
                        customer.textContent = ticket.customer_name;
                        row.append(id, complaint, customer, category, priority, status);
                    }
                }
                tbody.appendChild(row);
            });
        }

        function filteredTickets() {
            const query = state.search.trim().toLowerCase();
            return state.tickets.filter(ticket => {
                const matchesStatus = state.activeStatus === "all" || ticket.status === state.activeStatus;
                const haystack = [ticket.ticket_id, ticket.title, ticket.complaint, ticket.customer_name, ticket.category, ticket.urgency, ticket.status].join(" ").toLowerCase();
                return matchesStatus && (!query || haystack.includes(query));
            });
        }

        function renderTickets() {
            const filtered = filteredTickets();
            renderRows(byId("ticketsBody"), filtered, 6, false);
            renderTicketDetails();
            setText("ticketResultCount", `${filtered.length} ${filtered.length === 1 ? "ticket" : "tickets"}`);
        }

        function renderTicketDetails() {
            const panel = byId("ticketDetails");
            panel.replaceChildren();
            const ticket = state.tickets.find(item => item.ticket_id === state.selectedId);
            if (!ticket) {
                const empty = document.createElement("div");
                empty.className = "detail-empty";
                empty.textContent = "Select a ticket to review its complaint, response, and policy sources.";
                panel.appendChild(empty);
                return;
            }
            const id = document.createElement("div");
            id.className = "detail-id";
            id.textContent = ticket.ticket_id;
            const title = document.createElement("h3");
            title.className = "detail-title";
            title.textContent = ticket.title;
            const meta = document.createElement("div");
            meta.className = "detail-meta";
            meta.append(makePill(ticket.status, `status-pill ${statusClass(ticket.status)}`));
            meta.append(makePill(ticket.urgency, `priority-pill ${priorityClass(ticket.urgency)}`));
            const confidence = ticket.confidence == null ? "Confidence not recorded" : `Confidence ${(ticket.confidence * 100).toFixed(0)}%`;
            meta.append(makePill(confidence, "confidence-pill"));
            panel.append(id, title, meta);

            addDetailSection(panel, "Customer", `${ticket.customer_name}${ticket.order_id && ticket.order_id !== "N/A" ? ` · ${ticket.order_id}` : ""}`);
            addDetailSection(panel, "Complaint", ticket.complaint || "No complaint text recorded.");
            addDetailSection(panel, "Resolution", ticket.response || "No response recorded.");
            if (ticket.status === "Escalated" && ticket.escalation_reason && ticket.escalation_reason !== "None") {
                addDetailSection(panel, "Escalation reason", ticket.escalation_reason);
            }
            const sourceSection = document.createElement("section");
            sourceSection.className = "detail-section";
            const sourceLabel = document.createElement("div");
            sourceLabel.className = "detail-label";
            sourceLabel.textContent = "Policy sources";
            const sourceList = document.createElement("div");
            sourceList.className = "detail-sources";
            const sources = ticket.kb_sources.split(",").map(source => source.trim()).filter(source => source && source !== "None");
            if (sources.length) {
                sources.forEach(source => {
                    const chip = document.createElement("span");
                    chip.className = "source-chip";
                    chip.textContent = source;
                    sourceList.appendChild(chip);
                });
            } else {
                const none = document.createElement("span");
                none.className = "subtle";
                none.textContent = "No policy source recorded.";
                sourceList.appendChild(none);
            }
            sourceSection.append(sourceLabel, sourceList);
            panel.appendChild(sourceSection);
        }

        function addDetailSection(parent, label, value) {
            const section = document.createElement("section");
            section.className = "detail-section";
            const heading = document.createElement("div");
            heading.className = "detail-label";
            heading.textContent = label;
            const copy = document.createElement("p");
            copy.className = "detail-copy";
            copy.textContent = value;
            section.append(heading, copy);
            parent.appendChild(section);
        }

        function renderAgents() {
            const container = byId("agentCards");
            container.replaceChildren();
            agentDefinitions.forEach((agent, index) => {
                const card = document.createElement("article");
                card.className = "agent-card";
                const head = document.createElement("div");
                head.className = "agent-card-head";
                const icon = document.createElement("span");
                icon.className = "agent-icon";
                icon.style.setProperty("--agent", agent.color);
                icon.style.setProperty("--agent-tint", agent.tint);
                icon.textContent = String(index + 1).padStart(2, "0");
                const nameWrap = document.createElement("div");
                const name = document.createElement("div");
                name.className = "agent-name";
                name.textContent = agent.name;
                const role = document.createElement("div");
                role.className = "agent-role";
                role.textContent = agent.role;
                nameWrap.append(name, role);
                head.append(icon, nameWrap);
                const stateLabel = document.createElement("span");
                stateLabel.className = "agent-state";
                stateLabel.textContent = "Ready";
                head.appendChild(stateLabel);
                const description = document.createElement("p");
                description.className = "agent-output";
                description.textContent = agent.description;
                card.append(head, description);
                container.appendChild(card);
            });

            const execution = byId("executionSteps");
            execution.replaceChildren();
            const steps = state.lastWorkflow?.agent_steps || [];
            setText("executionSubtitle", state.lastWorkflow
                ? `Latest run · ${state.lastWorkflow.ticket_id} · ${state.lastWorkflow.status}`
                : "Submit a ticket to inspect the returned workflow steps.");
            if (!steps.length) {
                const empty = document.createElement("p");
                empty.className = "agent-output empty";
                empty.textContent = "Agent outputs will appear here after a complaint is processed.";
                execution.appendChild(empty);
                return;
            }
            steps.forEach(step => {
                const card = document.createElement("article");
                card.className = "agent-card";
                const head = document.createElement("div");
                head.className = "agent-card-head";
                const name = document.createElement("div");
                name.className = "agent-name";
                name.textContent = step.agent_name || "Workflow step";
                const role = document.createElement("div");
                role.className = "agent-role";
                role.textContent = step.role || "";
                const names = document.createElement("div");
                names.append(name, role);
                head.appendChild(names);
                const output = document.createElement("p");
                output.className = "agent-output";
                output.textContent = step.content || "No output was returned.";
                card.append(head, output);
                execution.appendChild(card);
            });
        }

        function renderKnowledgeCards() {
            const container = byId("knowledgeCards");
            container.replaceChildren();
            knowledgeDocuments.forEach(([file, category, description]) => {
                const card = document.createElement("article");
                card.className = "kb-card";
                const icon = document.createElement("div");
                icon.className = "kb-card-icon";
                icon.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 1 4 17.5v-12Z"/><path d="M8 7h8M8 10h6"/></svg>';
                const title = document.createElement("div");
                title.className = "kb-card-title";
                title.textContent = file;
                const copy = document.createElement("div");
                copy.className = "kb-card-copy";
                copy.textContent = `${category} · ${description}`;
                card.append(icon, title, copy);
                container.appendChild(card);
            });
        }

        async function searchKnowledge(event) {
            event.preventDefault();
            const query = byId("knowledgeQuery").value.trim();
            if (query.length < 2) {
                byId("knowledgeQuery").reportValidity();
                return;
            }
            const button = byId("knowledgeSearchButton");
            button.disabled = true;
            setText("knowledgeResultLabel", "Searching the company policy library…");
            try {
                const params = new URLSearchParams({ query, top_k: "5" });
                const category = byId("knowledgeCategory").value;
                if (category) params.set("category", category);
                const results = await apiRequest(`/api/search?${params.toString()}`);
                renderKnowledgeResults(results);
            } catch (error) {
                setText("knowledgeResultLabel", `Search failed: ${error.message}`);
                byId("knowledgeResults").replaceChildren();
                showToast(`Knowledge search failed: ${error.message}`, "error");
            } finally {
                button.disabled = false;
            }
        }

        function renderKnowledgeResults(result) {
            const container = byId("knowledgeResults");
            container.replaceChildren();
            const passages = Array.isArray(result.passages) ? result.passages : [];
            setText("knowledgeResultLabel", result.found
                ? `${passages.length} relevant passage${passages.length === 1 ? "" : "s"} · ${result.sources.join(", ") || "No named source"}`
                : result.resolution_notes || "No matching policy passage found.");
            if (!passages.length) {
                const empty = document.createElement("p");
                empty.className = "subtle";
                empty.textContent = result.resolution_notes || "No policy passages matched this search.";
                container.appendChild(empty);
                return;
            }
            passages.forEach(passage => {
                const card = document.createElement("article");
                card.className = "search-result";
                const head = document.createElement("div");
                head.className = "search-result-head";
                const source = document.createElement("span");
                source.className = "search-result-source";
                source.textContent = `${passage.file_name || "Policy"} · ${passage.section || "Section"}`;
                const score = document.createElement("span");
                score.className = "search-result-score";
                score.textContent = Number.isFinite(Number(passage.score)) ? `Relevance ${Number(passage.score).toFixed(2)}` : "";
                const copy = document.createElement("p");
                copy.className = "search-result-content";
                copy.textContent = passage.content || "";
                head.append(source, score);
                card.append(head, copy);
                container.appendChild(card);
            });
        }

        function renderDistribution(container, distribution, colorClass = "") {
            container.replaceChildren();
            const entries = Object.entries(distribution || {}).sort((a, b) => b[1] - a[1]);
            if (!entries.length) {
                const empty = document.createElement("p");
                empty.className = "subtle";
                empty.textContent = "No ticket data available.";
                container.appendChild(empty);
                return;
            }
            const max = Math.max(...entries.map(([, count]) => Number(count) || 0), 1);
            entries.forEach(([label, count]) => {
                const row = document.createElement("div");
                row.className = "distribution-row";
                const name = document.createElement("span");
                name.textContent = label;
                const track = document.createElement("span");
                track.className = "bar-track";
                const bar = document.createElement("span");
                bar.className = `bar-fill ${colorClass}`;
                bar.style.display = "block";
                bar.style.width = `${Math.max(0, (Number(count) / max) * 100)}%`;
                track.appendChild(bar);
                const value = document.createElement("span");
                value.className = "distribution-count";
                value.textContent = String(count);
                row.append(name, track, value);
                container.appendChild(row);
            });
        }

        function renderAnalytics() {
            const data = state.analytics;
            if (!data) return;
            const total = Number(data.total_tickets || 0);
            const resolved = Number(data.resolved_count || 0);
            const resolutionRate = total ? (resolved / total) * 100 : 0;
            setText("analyticsTotal", total);
            setText("analyticsResolutionRate", `${resolutionRate.toFixed(1)}%`);
            setText("analyticsConfidence", `${(Number(data.avg_confidence || 0) * 100).toFixed(0)}%`);
            setText("analyticsEscalationRate", `${Number(data.escalation_rate || 0).toFixed(1)}%`);
            renderDistribution(byId("categoryDistribution"), data.categories);
            renderDistribution(byId("urgencyDistribution"), data.urgencies, "teal");
            renderDistribution(byId("sentimentDistribution"), data.sentiments, "red");
        }

        async function runEvaluation() {
            const button = byId("runEvaluation");
            const results = byId("evaluationResults");
            button.disabled = true;
            results.hidden = false;
            results.textContent = "Running local benchmark cases…";
            try {
                const report = await apiRequest("/api/evaluation/run");
                const lines = [
                    `${report.total_cases ?? "?"} benchmark cases`,
                    `Status checks: ${report.all_status_passed ? "passed" : "not all passed"}`,
                    `Answer correctness: ${report.avg_answer_correctness ?? "n/a"}`,
                    `Faithfulness: ${report.avg_faithfulness ?? "n/a"}`,
                    `Hallucination rate: ${report.avg_hallucination_rate ?? "n/a"}`,
                    `Escalation accuracy: ${report.avg_escalation_accuracy ?? "n/a"}`
                ];
                results.textContent = lines.join("\n");
                if (Array.isArray(report.results)) {
                    report.results.forEach(item => {
                        lines.push(`Case ${item.case_id}: ${item.actual_status} (${item.status_match ? "pass" : "check"})`);
                    });
                    results.textContent = lines.join("\n");
                }
                showToast("Benchmark evaluation completed.");
                await refreshDashboard(false);
            } catch (error) {
                results.textContent = `Evaluation failed: ${error.message}`;
                showToast(`Evaluation failed: ${error.message}`, "error");
            } finally {
                button.disabled = false;
            }
        }

        function openTicketDialog() {
            byId("formError").hidden = true;
            byId("ticketDialog").showModal();
            byId("customerName").focus();
        }

        function closeTicketDialog() {
            if (byId("ticketDialog").open) byId("ticketDialog").close();
        }

        async function submitTicket(event) {
            event.preventDefault();
            const complaint = byId("complaint").value.trim();
            const errorElement = byId("formError");
            errorElement.hidden = true;
            if (complaint.length < 3 || complaint.length > 4000) {
                errorElement.textContent = "Enter a complaint between 3 and 4,000 characters.";
                errorElement.hidden = false;
                return;
            }
            const button = byId("submitTicket");
            button.disabled = true;
            button.textContent = "Processing…";
            try {
                const result = await apiRequest("/api/process-complaint", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        complaint,
                        customer_name: byId("customerName").value.trim(),
                        order_id: byId("orderId").value.trim()
                    })
                });
                state.lastWorkflow = result;
                state.workflowByTicket.set(result.ticket_id, result);
                state.selectedId = result.ticket_id;
                closeTicketDialog();
                byId("ticketForm").reset();
                setText("complaintLength", "0 / 4,000");
                await refreshDashboard(false);
                setPage("tickets");
                showToast(`Ticket ${result.ticket_id} ${result.status.toLowerCase()}.`);
            } catch (error) {
                errorElement.textContent = `Could not process complaint: ${error.message}`;
                errorElement.hidden = false;
                showToast(`Ticket processing failed: ${error.message}`, "error");
            } finally {
                button.disabled = false;
                button.textContent = "Process complaint";
            }
        }

        function renderPresets() {
            const container = byId("presetButtons");
            presets.forEach(preset => {
                const button = document.createElement("button");
                button.className = "preset-button";
                button.type = "button";
                button.textContent = preset.name;
                button.addEventListener("click", () => {
                    byId("customerName").value = preset.customer;
                    byId("orderId").value = preset.order;
                    byId("complaint").value = preset.complaint;
                    setText("complaintLength", `${preset.complaint.length} / 4,000`);
                });
                container.appendChild(button);
            });
        }

        document.querySelectorAll(".nav-link[data-page]").forEach(button => {
            button.addEventListener("click", () => setPage(button.dataset.page));
        });
        document.querySelectorAll("[data-page-link]").forEach(button => {
            button.addEventListener("click", event => {
                event.preventDefault();
                setPage(button.dataset.pageLink);
            });
        });
        document.querySelectorAll("[data-refresh]").forEach(button => {
            button.addEventListener("click", () => refreshDashboard(true));
        });
        document.querySelectorAll("[data-status-filter]").forEach(button => {
            button.addEventListener("click", () => {
                state.activeStatus = button.dataset.statusFilter;
                document.querySelectorAll("[data-status-filter]").forEach(chip => chip.classList.toggle("active", chip === button));
                renderTickets();
            });
        });

        byId("ticketSearch").addEventListener("input", event => {
            state.search = event.target.value;
            renderTickets();
        });
        byId("refreshButton").addEventListener("click", () => refreshDashboard(true));
        byId("newTicketButton").addEventListener("click", openTicketDialog);
        byId("agentsNewTicket").addEventListener("click", openTicketDialog);
        byId("closeDialog").addEventListener("click", closeTicketDialog);
        byId("cancelDialog").addEventListener("click", closeTicketDialog);
        byId("ticketForm").addEventListener("submit", submitTicket);
        byId("complaint").addEventListener("input", event => setText("complaintLength", `${event.target.value.length} / 4,000`));
        byId("knowledgeSearchForm").addEventListener("submit", searchKnowledge);
        byId("runEvaluation").addEventListener("click", runEvaluation);
        byId("downloadTickets").href = apiUrl("/api/tickets/download");
        byId("ticketDialog").addEventListener("click", event => {
            if (event.target === byId("ticketDialog")) closeTicketDialog();
        });
        byId("ticketDialog").addEventListener("close", () => byId("newTicketButton").focus());

        renderPresets();
        renderWorkflowCards(byId("overviewWorkflow"), false);
        renderKnowledgeCards();
        renderAgents();
        refreshDashboard();
