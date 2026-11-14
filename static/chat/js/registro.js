document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('registroForm');
    const password = document.getElementById('password');
    const confirmPassword = document.getElementById('confirm_password');

    const validators = [
        {
            input: document.getElementById('cedulaInput'),
            feedback: document.getElementById('cedulaFeedback'),
            validate: value => /^\d{7,8}$/.test(value),
            error: 'Ingresa entre 7 y 8 dígitos, solo números.',
            success: 'Cédula válida.',
        },
        {
            input: document.getElementById('telefonoInput'),
            feedback: document.getElementById('telefonoFeedback'),
            validate: value => /^\d{11}$/.test(value),
            error: 'Ingresa exactamente 11 dígitos, solo números.',
            success: 'Teléfono válido.',
        },
        {
            input: document.getElementById('correoInput'),
            feedback: document.getElementById('correoFeedback'),
            validate: value => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
            error: 'Ingresa un correo electrónico válido.',
            success: 'Correo electrónico válido.',
        },
    ];

    validators.forEach(({ input, feedback, validate, error, success }) => {
        if (!input || !feedback) return;
        input.addEventListener('input', () => {
            const value = input.value.trim();
            feedback.textContent = value ? (validate(value) ? success : error) : '';
            feedback.classList.toggle('is-valid', Boolean(value) && validate(value));
            feedback.classList.toggle('is-invalid', Boolean(value) && !validate(value));
            input.setAttribute('aria-invalid', String(Boolean(value) && !validate(value)));
        });
    });

    const requirements = [
        [document.getElementById('reqLength'), value => value.length >= 16],
        [document.getElementById('reqUppercase'), value => /[A-Z]/.test(value)],
        [document.getElementById('reqLowercase'), value => /[a-z]/.test(value)],
        [document.getElementById('reqNumber'), value => /\d/.test(value)],
        [document.getElementById('reqSpecial'), value => /[!@#$%^&*(),.?":{}|<>]/.test(value)],
    ];

    function updatePasswordRequirements() {
        if (!password) return;
        requirements.forEach(([element, isValid]) => {
            if (!element) return;
            const met = isValid(password.value);
            element.classList.toggle('requirement-met', met);
            const icon = element.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-circle', !met);
                icon.classList.toggle('fa-circle-check', met);
            }
        });
        if (confirmPassword) confirmPassword.setCustomValidity('');
    }

    password?.addEventListener('input', updatePasswordRequirements);
    confirmPassword?.addEventListener('input', () => confirmPassword.setCustomValidity(''));

    function setupPasswordToggle(buttonId, inputId, iconId) {
        const button = document.getElementById(buttonId);
        const input = document.getElementById(inputId);
        const icon = document.getElementById(iconId);
        button?.addEventListener('click', () => {
            if (!input || !icon) return;
            input.type = input.type === 'password' ? 'text' : 'password';
            icon.classList.toggle('fa-eye');
            icon.classList.toggle('fa-eye-slash');
        });
    }

    setupPasswordToggle('togglePassword', 'password', 'eyeIconPassword');
    setupPasswordToggle('toggleConfirm', 'confirm_password', 'eyeIconConfirm');

    form?.addEventListener('submit', event => {
        if (password && confirmPassword && password.value !== confirmPassword.value) {
            event.preventDefault();
            confirmPassword.setCustomValidity('Las contraseñas no coinciden.');
            confirmPassword.reportValidity();
        }
    });
});
