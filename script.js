
const isLocalFrontend = ["localhost", "127.0.0.1"].includes(
    window.location.hostname
);
const API_URL = window.CAMPUSFIND_API_URL || (
    window.location.protocol === "file:" ||
    (isLocalFrontend && window.location.port !== "5000")
        ? "http://127.0.0.1:5000/api"
        : `${window.location.origin}/api`
);

// =====================================
// BROWSE ITEMS: SEARCH AND FILTERS
// =====================================

const searchInput = document.getElementById("searchInput");
const itemList = document.getElementById("itemList");
const filterButtons = document.querySelectorAll(".filter");

if (searchInput && itemList) {
    let activeFilter = "All";
    const emptyState = document.getElementById("emptyState");

    async function loadItems() {
        const params = new URLSearchParams();
        const query = searchInput.value.trim();

        if (query) {
            params.set("q", query);
        }

        if (activeFilter !== "All") {
            params.set("status", activeFilter.toLowerCase());
        }

        try {
            const response = await fetch(
                `${API_URL}/items?${params.toString()}`
            );

            if (!response.ok) {
                throw new Error("Could not load items.");
            }

            const items = await response.json();
            itemList.replaceChildren();

            items.forEach(item => {
                const card = document.createElement("article");
                card.className = "item-card";
                card.tabIndex = 0;
                card.setAttribute("role", "link");
                card.setAttribute(
                    "aria-label",
                    `View details for ${item.title || "item"}`
                );
                const openDetails = () => {
                    window.location.href =
                        `item.html?id=${encodeURIComponent(item.id)}`;
                };
                card.addEventListener("click", openDetails);
                card.addEventListener("keydown", event => {
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openDetails();
                    }
                });

                // Item photo
                if (item.image_url) {
                    const photo = document.createElement("img");
                    photo.className = "item-photo";
                    photo.alt = `Photo of ${item.title || "item"}`;
                    photo.loading = "lazy";
                    photo.src = item.image_url;
                    photo.onerror = () => photo.remove();

                    card.appendChild(photo);
                }

                // Item title
                const title = document.createElement("h3");
                title.textContent = item.title || "Untitled item";

                // Lost = red; Found = green
                const status = document.createElement("span");
                const normalizedStatus =
                    (item.status || "").toLowerCase();

                status.className = `status ${normalizedStatus}`;
                status.textContent = normalizedStatus.toUpperCase();

                // Category and location
                const details = document.createElement("p");
                details.textContent =
                    `${item.category || "Other"} · ${item.location || "Location not specified"}`;

                // Description
                const description = document.createElement("p");
                description.textContent = item.description || "";

                card.append(title, status, details, description);
                itemList.appendChild(card);
            });

            if (emptyState) {
                emptyState.hidden = items.length > 0;

                if (items.length === 0) {
                    emptyState.textContent = "No matching items found.";
                }
            }
        } catch (error) {
            console.error("Error loading items:", error);

            if (emptyState) {
                emptyState.hidden = false;
                emptyState.textContent =
                    "Unable to load items. Please check that the backend is running.";
            }
        }
    }

    searchInput.addEventListener("input", loadItems);

    filterButtons.forEach(button => {
        button.addEventListener("click", () => {
            activeFilter = button.dataset.filter || "All";

            filterButtons.forEach(item => {
                const active = item === button;
                item.classList.toggle("active", active);
                item.setAttribute("aria-pressed", String(active));
            });

            loadItems();
        });
    });

    loadItems();
}

// =====================================
// ITEM DETAILS
// =====================================

const detailContainer = document.getElementById("itemDetails");

if (detailContainer) {
    const params = new URLSearchParams(window.location.search);
    const itemId = params.get("id");
    const confirmToken = params.get("confirmToken");
    const detailMessage = document.getElementById("detailMessage");

    function addDetail(label, value) {
        const row = document.createElement("div");
        row.className = "detail-row";
        const heading = document.createElement("h2");
        heading.textContent = label;
        const content = document.createElement("p");
        content.textContent = value || "Not provided";
        row.append(heading, content);
        return row;
    }

    async function loadItemDetails() {
        if (!itemId || !/^\d+$/.test(itemId)) {
            detailMessage.textContent = "This item link is invalid.";
            return;
        }

        try {
            const response = await fetch(`${API_URL}/items/${encodeURIComponent(itemId)}`);
            const item = await response.json();
            if (!response.ok) throw new Error(item.error || "Could not load this item.");
            detailMessage.hidden = true;

            const title = document.getElementById("detailTitle");
            title.textContent = item.title || "Untitled item";
            const status = document.getElementById("detailStatus");
            status.className = `status ${item.is_resolved ? "resolved" : (item.status || "").toLowerCase()}`;
            status.textContent = item.is_resolved
                ? "REUNITED"
                : (item.status || "").toUpperCase();

            const contactForm = document.getElementById("contactForm");
            const contactMessage = document.getElementById("contactMessage");
            const contactCard = contactForm.closest(".contact-card");
            contactCard.hidden = Boolean(item.is_resolved || confirmToken);
            if (item.is_resolved) {
                contactCard.hidden = false;
                contactForm.hidden = true;
                contactMessage.textContent = "This report has already been marked reunited.";
            }

            contactForm.addEventListener("submit", async event => {
                event.preventDefault();
                const sendButton = contactForm.querySelector('button[type="submit"]');
                sendButton.disabled = true;
                contactMessage.textContent = "Sending your message…";
                try {
                    const contactResponse = await fetch(
                        `${API_URL}/items/${encodeURIComponent(itemId)}/contact`,
                        {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                name: contactForm.elements.name.value.trim(),
                                email: contactForm.elements.email.value.trim(),
                                message: contactForm.elements.message.value.trim()
                            })
                        }
                    );
                    const result = await contactResponse.json();
                    if (!contactResponse.ok) {
                        throw new Error(result.error || "Could not send your message.");
                    }
                    contactForm.reset();
                    contactMessage.textContent = result.message;
                } catch (error) {
                    contactMessage.textContent = error.message;
                } finally {
                    sendButton.disabled = false;
                }
            });

            const confirmation = document.getElementById("returnConfirmation");
            const confirmButton = document.getElementById("confirmReturn");
            const confirmMessage = document.getElementById("confirmMessage");
            if (confirmToken) {
                confirmation.hidden = false;
                if (item.is_resolved) {
                    confirmButton.hidden = true;
                    confirmMessage.textContent = "This report has already been marked reunited.";
                } else {
                    confirmButton.addEventListener("click", async () => {
                        confirmButton.disabled = true;
                        confirmMessage.textContent = "Confirming…";
                        try {
                            const confirmResponse = await fetch(
                                `${API_URL}/items/${encodeURIComponent(itemId)}/confirm-return`,
                                {
                                    method: "POST",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({ token: confirmToken })
                                }
                            );
                            const result = await confirmResponse.json();
                            if (!confirmResponse.ok) {
                                throw new Error(result.error || "Could not confirm the return.");
                            }
                            status.className = "status resolved";
                            status.textContent = "REUNITED";
                            confirmButton.hidden = true;
                            confirmMessage.textContent = result.message;
                            history.replaceState({}, "", `item.html?id=${encodeURIComponent(itemId)}`);
                        } catch (error) {
                            confirmButton.disabled = false;
                            confirmMessage.textContent = error.message;
                        }
                    }, { once: true });
                }
            }

            const photo = document.getElementById("detailPhoto");
            if (item.image_url) {
                photo.src = item.image_url;
                photo.alt = `Photo of ${item.title || "item"}`;
                photo.hidden = false;
                photo.onerror = () => { photo.hidden = true; };
            }

            const reportedAt = item.created_at
                ? new Date(item.created_at).toLocaleString()
                : "Not provided";
            const fields = [
                ["Description", item.description],
                ["Category", item.category],
                ["Location", item.location],
                ["Report submitted", reportedAt]
            ];
            const details = document.getElementById("detailFields");
            fields.forEach(([label, value]) => details.appendChild(addDetail(label, value)));
            detailContainer.hidden = false;

        } catch (error) {
            detailMessage.hidden = false;
            detailMessage.textContent = error.message ||
                "Unable to load this item. Please check that the backend is running.";
        }
    }

    loadItemDetails();
}


// =====================================
// REPORT ITEM: SUBMIT TEXT AND PHOTO
// =====================================

const reportForm = document.getElementById("reportForm");

if (reportForm) {
    reportForm.addEventListener("submit", async event => {
        event.preventDefault();

        const message = document.getElementById("formMessage");
        const submitButton = reportForm.querySelector(
            'button[type="submit"]'
        );

        const contact = reportForm.elements.contact.value.trim();

        // Validate email
        const isEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact);

        if (!isEmail) {
            message.textContent =
                "Please enter a valid email address.";
            return;
        }

        // Validate optional image
        const imageInput = document.getElementById("itemImage");
        const imageFile = imageInput?.files?.[0];

        if (imageFile) {
            const allowedTypes = [
                "image/jpeg",
                "image/png",
                "image/webp",
                "image/gif"
            ];

            if (!allowedTypes.includes(imageFile.type)) {
                message.textContent =
                    "Please choose a JPG, PNG, WEBP or GIF image.";
                return;
            }

            if (imageFile.size > 5 * 1024 * 1024) {
                message.textContent =
                    "Please choose an image smaller than 5 MB.";
                return;
            }
        }

        // Prepare form data
        const formData = new FormData();

        formData.append(
            "title",
            reportForm.elements.itemName.value.trim()
        );
        formData.append(
            "description",
            reportForm.elements.description.value.trim()
        );
        formData.append(
            "status",
            reportForm.elements.reportType.value.toLowerCase()
        );
        formData.append(
            "location",
            reportForm.elements.location.value.trim()
        );
        formData.append(
            "category",
            reportForm.elements.category.value.trim()
        );
        formData.append(
            "reporter_name",
            reportForm.elements.reporterName.value.trim()
        );
        formData.append("reporter_email", contact);

        if (imageFile) {
            formData.append("image", imageFile);
        }

        try {
            submitButton.disabled = true;
            message.textContent = "Submitting report...";

            const response = await fetch(`${API_URL}/items`, {
                method: "POST",
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(
                    result.error || "Report submission failed."
                );
            }

            // Redirect only after successful submission.
            reportForm.reset();

            message.textContent = "Report submitted successfully!";

        } catch (error) {
            console.error("Error submitting report:", error);

            message.textContent =
                `${error.message} Make sure the backend is running.`;
        } finally {
            submitButton.disabled = false;
        }
    });
}
