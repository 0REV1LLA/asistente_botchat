function showError(message) {
    const errorBox = document.getElementById('errorBox');
    errorBox.textContent = message;
    errorBox.hidden = false;
}

function hideError() {
    const errorBox = document.getElementById('errorBox');
    errorBox.hidden = true;
    errorBox.textContent = '';
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('loginForm');
    const submitBtn = document.getElementById('submitBtn');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const errorBox = document.getElementById('errorBox');

    if (errorBox && !errorBox.hidden && errorBox.textContent.trim()) {
        loadingOverlay.hidden = true;
        loadingOverlay.style.display = 'none';
    }
    let isSubmitting = false;

    form.addEventListener('submit', (event) => {
        if (isSubmitting) {
            return;
        }

        event.preventDefault();
        hideError();

        isSubmitting = true;
        loadingOverlay.hidden = false;
        loadingOverlay.style.display = 'grid';
        submitBtn.disabled = true;

        setTimeout(() => {
            HTMLFormElement.prototype.submit.call(form);
        }, 1800);
    });
});
