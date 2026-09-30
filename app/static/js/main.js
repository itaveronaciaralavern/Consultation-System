// Small progressive-enhancement helpers. No frontend framework, per spec.
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            const message = form.getAttribute("data-confirm");
            if (!window.confirm(message)) {
                e.preventDefault();
            }
        });
    });
});
