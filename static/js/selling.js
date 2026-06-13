(function () {
    var signinCard = document.getElementById("signin-card");
    var sellerCard = document.getElementById("seller-card");
    var myListingsCard = document.getElementById("my-listings-card");
    var usernameInput = document.getElementById("username");
    var bankAccNum = document.getElementById("bankaccnum");
    var signinBtn = document.getElementById("signin-btn");
    var signinMsg = document.getElementById("signin-msg");
    var sellerWelcome = document.getElementById("seller-welcome");
    var productName = document.getElementById("product-name");
    var productImage = document.getElementById("product-image");
    var productQuantity = document.getElementById("product-quantity");
    var productPrice = document.getElementById("product-price");
    var listBtn = document.getElementById("list-btn");
    var signoutBtn = document.getElementById("signout-btn");
    var listMsg = document.getElementById("list-msg");
    var myListings = document.getElementById("my-listings");

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

    function showSignedIn(user) {
        signinCard.style.display = "none";
        sellerCard.style.display = "";
        myListingsCard.style.display = "";
        sellerWelcome.textContent = "Signed in as " + user.username + " (" + user.macho_bucks + " Macho Bucks)";
        loadMyListings();
    }

    function showSignedOut() {
        signinCard.style.display = "";
        sellerCard.style.display = "none";
        myListingsCard.style.display = "none";
        sellerWelcome.textContent = "";
        myListings.innerHTML = "";
        listMsg.textContent = "";
        signinMsg.textContent = "";
    }

    function statusLabel(status) {
        if (status === "approved") return "Approved";
        if (status === "rejected") return "Rejected";
        return "Pending approval";
    }

    function loadMyListings() {
        myListings.innerHTML = "";

        fetchJson("/api/products/mine", { credentials: "include" })
            .then(function (res) {
                if (!res.ok) {
                    myListings.textContent = res.d.error || "Could not load listings";
                    return;
                }
                if (!res.d.length) {
                    myListings.textContent = "No listings yet.";
                    return;
                }
                res.d.forEach(function (product) {
                    var row = document.createElement("div");
                    row.className = "listing-row";
                    row.textContent = product.name + " — " + statusLabel(product.status) +
                        " — qty " + product.quantity + " — " + Number(product.price).toFixed(2) + " M$";
                    myListings.appendChild(row);
                });
            })
            .catch(function () {
                myListings.textContent = "Network error";
            });
    }

    signinBtn.addEventListener("click", function () {
        signinMsg.textContent = "";
        var username = usernameInput.value.trim();
        var bankAccountNumber = bankAccNum.value.trim();

        if (!username || !bankAccountNumber) {
            signinMsg.textContent = "Username and bank account number are required.";
            return;
        }

        fetchJson("/api/session", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: username,
                bank_account_number: bankAccountNumber,
            }),
        }).then(function (res) {
            if (!res.ok) {
                signinMsg.textContent = res.d.error || "Sign in failed";
                return;
            }
            showSignedIn(res.d.user);
        }).catch(function () {
            signinMsg.textContent = "Network error";
        });
    });

    signoutBtn.addEventListener("click", function () {
        fetchJson("/api/session", {
            method: "DELETE",
            credentials: "include",
        }).finally(function () {
            showSignedOut();
        });
    });

    listBtn.addEventListener("click", function () {
        listMsg.textContent = "";
        var name = productName.value.trim();
        var quantity = productQuantity.value.trim();
        var price = productPrice.value.trim();
        var imageFile = productImage.files[0];

        if (!name || !quantity || !price || !imageFile) {
            listMsg.textContent = "Name, image, quantity, and price are required.";
            return;
        }

        readImageAsDataUrl(imageFile).then(function (imageData) {
            return fetchJson("/api/products", {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: name,
                    image_data: imageData,
                    quantity: Number(quantity),
                    price: Number(price),
                }),
            });
        }).then(function (res) {
            if (!res.ok) {
                listMsg.textContent = res.d.error || "Could not submit listing";
                return;
            }
            listMsg.textContent = "Listing submitted for admin approval.";
            productName.value = "";
            productImage.value = "";
            productQuantity.value = "";
            productPrice.value = "";
            loadMyListings();
        }).catch(function (err) {
            listMsg.textContent = err.message || "Could not submit listing";
        });
    });

    fetchJson("/api/session", { credentials: "include" })
        .then(function (res) {
            if (res.ok && res.d.signed_in) {
                showSignedIn(res.d.user);
            }
        });
})();
