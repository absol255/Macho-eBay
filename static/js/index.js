(function () {
    var shopMsg = document.getElementById("shop-msg");
    var shopGrid = document.getElementById("shop-grid");

    function fetchJson(url, options) {
        return fetch(url, options).then(function (r) {
            return r.json().then(function (d) {
                return { ok: r.ok, d: d };
            });
        });
    }

    function formatPrice(price) {
        
        return Number(price).toFixed(2) + " M$";
    }

    function createBuyCard(product) {
        var card = document.createElement("div");
        card.className = "product-card";

        var img = document.createElement("img");
        img.className = "product-image";
        img.src = product.image_data;
        img.alt = product.name;

        var title = document.createElement("h3");
        title.textContent = product.name;

        var seller = document.createElement("p");
        seller.className = "product-meta";
        seller.textContent = "Seller: " + product.seller_username;

        var price = document.createElement("p");
        price.className = "product-price";
        price.textContent = formatPrice(product.price) + " each";

        var stock = document.createElement("p");
        stock.className = "product-meta";
        stock.textContent = "In stock: " + product.quantity;

        var usernameInput = document.createElement("input");
        usernameInput.type = "text";
        usernameInput.placeholder = "Your username";
        usernameInput.maxLength = 64;
        usernameInput.autocomplete = "username";

        var bankInput = document.createElement("input");
        bankInput.type = "text";
        bankInput.placeholder = "Bank account number";
        bankInput.inputMode = "numeric";
        bankInput.autocomplete = "off";

        var qtyInput = document.createElement("input");
        qtyInput.type = "number";
        qtyInput.placeholder = "Quantity";
        qtyInput.min = "1";
        qtyInput.max = String(product.quantity);
        qtyInput.step = "1";

        var buyBtn = document.createElement("button");
        buyBtn.className = "button";
        buyBtn.type = "button";
        buyBtn.textContent = "Buy";

        var msg = document.createElement("p");
        msg.className = "product-msg";

        buyBtn.addEventListener("click", function () {
            msg.textContent = "";
            var username = usernameInput.value.trim();
            var bankAccountNumber = bankInput.value.trim();
            var quantity = qtyInput.value.trim();

            if (!username || !bankAccountNumber || !quantity) {
                msg.textContent = "Username, bank account number, and quantity are required.";
                return;
            }

            fetchJson("/api/purchase", {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    product_id: product.id,
                    username: username,
                    bank_account_number: bankAccountNumber,
                    quantity: Number(quantity),
                }),
            }).then(function (res) {
                if (!res.ok) {
                    msg.textContent = res.d.error || "Purchase failed";
                    return;
                }
                msg.textContent = "Purchased for " + formatPrice(res.d.total) + ". Balance: " + formatPrice(res.d.remaining_balance);
                loadProducts();
            }).catch(function () {
                msg.textContent = "Network error";
            });
        });

        card.appendChild(img);
        card.appendChild(title);
        card.appendChild(seller);
        card.appendChild(price);
        card.appendChild(stock);
        card.appendChild(usernameInput);
        card.appendChild(bankInput);
        card.appendChild(qtyInput);
        card.appendChild(buyBtn);
        card.appendChild(msg);

        return card;
    }

    function loadProducts() {
        shopMsg.textContent = "";
        shopGrid.innerHTML = "";

        fetchJson("/api/products")
            .then(function (res) {
                if (!res.ok) {
                    shopMsg.textContent = res.d.error || "Could not load shop";
                    return;
                }
                if (!res.d.length) {
                    shopMsg.textContent = "No products in the shop yet.";
                    return;
                }
                res.d.forEach(function (product) {
                    shopGrid.appendChild(createBuyCard(product));
                });
            })
            .catch(function () {
                shopMsg.textContent = "Network error — could not reach /api/products";
            });
    }

    loadProducts();
})();
