(function () {
    var sellerUsername = document.getElementById("seller-username");
    var sellerBankAccNum = document.getElementById("seller-bankaccnum");
    var productName = document.getElementById("product-name");
    var productImage = document.getElementById("product-image");
    var productQuantity = document.getElementById("product-quantity");
    var productPrice = document.getElementById("product-price");
    var addBtn = document.getElementById("add-btn");
    var addMsg = document.getElementById("add-msg");
    var pendingMsg = document.getElementById("pending-msg");
    var pendingList = document.getElementById("pending-list");

    function fetchJson(url, options) {
        return fetch(url, options).then(function (r) {
            return r.json().then(function (d) {
                return { ok: r.ok, d: d };
            });
        });
    }

    function readImageAsDataUrl(file) {
        return new Promise(function (resolve, reject) {
            if (!file) {
                reject(new Error("No image selected"));
                return;
            }
            var reader = new FileReader();
            reader.onload = function () {
                resolve(reader.result);
            };
            reader.onerror = function () {
                reject(new Error("Could not read image"));
            };
            reader.readAsDataURL(file);
        });
    }

    function createPendingCard(product) {
        var card = document.createElement("div");
        card.className = "pending-card";

        var img = document.createElement("img");
        img.className = "product-image";
        img.src = product.image_data;
        img.alt = product.name;

        var title = document.createElement("h3");
        title.textContent = product.name;

        var meta = document.createElement("p");
        meta.className = "product-meta";
        meta.textContent = "Seller: " + product.seller_username +
            " — qty " + product.quantity +
            " — " + Number(product.price).toFixed(2) + " M$";

        var approveBtn = document.createElement("button");
        approveBtn.className = "button";
        approveBtn.type = "button";
        approveBtn.textContent = "Approve";

        var rejectBtn = document.createElement("button");
        rejectBtn.className = "button";
        rejectBtn.type = "button";
        rejectBtn.textContent = "Reject";

        var msg = document.createElement("p");
        msg.className = "product-msg";

        approveBtn.addEventListener("click", function () {
            msg.textContent = "";
            fetchJson("/api/products/" + product.id + "/approve", {
                method: "POST",
                credentials: "include",
            }).then(function (res) {
                if (!res.ok) {
                    msg.textContent = res.d.error || "Approve failed";
                    return;
                }
                loadPending();
            }).catch(function () {
                msg.textContent = "Network error";
            });
        });

        rejectBtn.addEventListener("click", function () {
            msg.textContent = "";
            fetchJson("/api/products/" + product.id + "/reject", {
                method: "POST",
                credentials: "include",
            }).then(function (res) {
                if (!res.ok) {
                    msg.textContent = res.d.error || "Reject failed";
                    return;
                }
                loadPending();
            }).catch(function () {
                msg.textContent = "Network error";
            });
        });

        card.appendChild(img);
        card.appendChild(title);
        card.appendChild(meta);
        card.appendChild(approveBtn);
        card.appendChild(rejectBtn);
        card.appendChild(msg);

        return card;
    }

    function loadPending() {
        pendingMsg.textContent = "";
        pendingList.innerHTML = "";

        fetchJson("/api/products/pending", { credentials: "include" })
            .then(function (res) {
                if (!res.ok) {
                    pendingMsg.textContent = res.d.error || "Could not load pending listings";
                    return;
                }
                if (!res.d.length) {
                    pendingMsg.textContent = "No pending listings.";
                    return;
                }
                res.d.forEach(function (product) {
                    pendingList.appendChild(createPendingCard(product));
                });
            })
            .catch(function () {
                pendingMsg.textContent = "Network error";
            });
    }

    addBtn.addEventListener("click", function () {
        addMsg.textContent = "";
        var username = sellerUsername.value.trim();
        var bankAccountNumber = sellerBankAccNum.value.trim();
        var name = productName.value.trim();
        var quantity = productQuantity.value.trim();
        var price = productPrice.value.trim();
        var imageFile = productImage.files[0];

        if (!username || !bankAccountNumber || !name || !quantity || !price || !imageFile) {
            addMsg.textContent = "Seller username, bank account, name, image, quantity, and price are required.";
            return;
        }

        readImageAsDataUrl(imageFile).then(function (imageData) {
            return fetchJson("/api/products", {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username: username,
                    bank_account_number: bankAccountNumber,
                    name: name,
                    image_data: imageData,
                    quantity: Number(quantity),
                    price: Number(price),
                }),
            });
        }).then(function (res) {
            if (!res.ok) {
                addMsg.textContent = res.d.error || "Could not add product";
                return;
            }
            addMsg.textContent = "Product added to the shop.";
            productName.value = "";
            productImage.value = "";
            productQuantity.value = "";
            productPrice.value = "";
            loadPending();
        }).catch(function (err) {
            addMsg.textContent = err.message || "Could not add product";
        });
    });

    loadPending();
})();
