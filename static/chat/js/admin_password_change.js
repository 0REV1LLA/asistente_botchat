document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('.password-change-form');
    const newPassword = document.getElementById('id_new_password');
    const confirmPassword = document.getElementById('id_confirm_password');
    const requirements = [
        [document.getElementById('adminReqLength'), value => value.length >= 16],
        [document.getElementById('adminReqUppercase'), value => /[A-Z]/.test(value)],
        [document.getElementById('adminReqLowercase'), value => /[a-z]/.test(value)],
        [document.getElementById('adminReqNumber'), value => /\d/.test(value)],
        [document.getElementById('adminReqSpecial'), value => /[!@#$%^&*(),.?":{}|<>]/.test(value)],
    ];

    document.querySelectorAll('[data-password-toggle]').forEach(button => {
        const input = document.getElementById(button.dataset.passwordToggle);
        const icon = button.querySelector('i');
        button.addEventListener('click', () => {
            if (!input || !icon) return;
            input.type = input.type === 'password' ? 'text' : 'password';
            icon.classList.toggle('fa-eye');
            icon.classList.toggle('fa-eye-slash');
        });
    });

    newPassword?.addEventListener('input', () => {
        requirements.forEach(([element, isValid]) => {
            if (!element) return;
            const met = isValid(newPassword.value);
            element.classList.toggle('requirement-met', met);
            const icon = element.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-circle', !met);
                icon.classList.toggle('fa-circle-check', met);
            }
        });
        confirmPassword?.setCustomValidity('');
    });
    confirmPassword?.addEventListener('input', () => confirmPassword.setCustomValidity(''));

    form?.addEventListener('submit', event => {
        if (newPassword && confirmPassword && newPassword.value !== confirmPassword.value) {
            event.preventDefault();
            confirmPassword.setCustomValidity('Las contraseñas no coinciden.');
            confirmPassword.reportValidity();
        }
    });
});
