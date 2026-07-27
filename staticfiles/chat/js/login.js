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

    const openBtn = document.getElementById('openNormativasBtn');
    const closeBtn = document.getElementById('closeNormativasBtn');
    const modal = document.getElementById('normativasModal');

    function openModal() {
        if (modal) {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    }

    function closeModal() {
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    if (openBtn) {
        openBtn.addEventListener('click', openModal);
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }

    // Cerrar al hacer clic fuera del modal
    if (modal) {
        modal.addEventListener('click', function(event) {
            if (event.target === modal) {
                closeModal();
            }
        });
    }

    // Cerrar con tecla Escape
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && modal && modal.style.display === 'flex') {
            closeModal();
        }
    });
});