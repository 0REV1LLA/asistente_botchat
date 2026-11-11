document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('loginForm');
    const submitBtn = document.getElementById('submitBtn');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const errorBox = document.getElementById('errorBox');
    const passwordInput = document.getElementById('password');
    const cedulaInput = document.getElementById('cedula');
    const cedulaFeedback = document.getElementById('loginCedulaFeedback');
    const togglePassword = document.getElementById('togglePassword');
    const eyeIcon = document.getElementById('eyeIconPassword');
    const blockedModal = document.getElementById('blockedModal');
    let isSubmitting = false;

    if (errorBox && !errorBox.hidden && errorBox.textContent.trim() && loadingOverlay) {
        loadingOverlay.hidden = true;
    }

    cedulaInput?.addEventListener('input', () => {
        if (!cedulaFeedback) return;
        const value = cedulaInput.value.trim();
        if (!value) {
            cedulaFeedback.textContent = '';
            cedulaFeedback.className = 'field-feedback';
            cedulaInput.setAttribute('aria-invalid', 'false');
            return;
        }
        if (value === 'SuperAdminFarmaLuz') {
            cedulaFeedback.textContent = 'Cuenta de superadministrador.';
            cedulaFeedback.className = 'field-feedback is-valid';
            cedulaInput.setAttribute('aria-invalid', 'false');
            return;
        }
        const valid = /^\d{7,8}$/.test(value);
        cedulaFeedback.textContent = valid
            ? 'Cédula válida.'
            : 'Ingresa entre 7 y 8 dígitos, solo números.';
        cedulaFeedback.className = valid
            ? 'field-feedback is-valid'
            : 'field-feedback is-invalid';
        cedulaInput.setAttribute('aria-invalid', String(!valid));
    });

    togglePassword?.addEventListener('click', () => {
        if (!passwordInput || !eyeIcon) return;
        passwordInput.type = passwordInput.type === 'password' ? 'text' : 'password';
        eyeIcon.classList.toggle('fa-eye');
        eyeIcon.classList.toggle('fa-eye-slash');
    });

    document.querySelector('[data-dismiss-blocked]')?.addEventListener('click', () => {
        blockedModal?.remove();
    });

    form?.addEventListener('submit', event => {
        if (isSubmitting || !loadingOverlay || !submitBtn) return;
        event.preventDefault();
        isSubmitting = true;
        loadingOverlay.hidden = false;
        submitBtn.disabled = true;
        window.setTimeout(() => HTMLFormElement.prototype.submit.call(form), 500);
    });
});
