document.addEventListener('DOMContentLoaded', () => {
    const password = document.getElementById('password');
    const confirmPassword = document.getElementById('confirm_password');
    const form = document.getElementById('resetForm');
    const requirements = [
        [document.getElementById('reqLength'), value => value.length >= 16],
        [document.getElementById('reqUppercase'), value => /[A-Z]/.test(value)],
        [document.getElementById('reqLowercase'), value => /[a-z]/.test(value)],
        [document.getElementById('reqNumber'), value => /\d/.test(value)],
        [document.getElementById('reqSpecial'), value => /[!@#$%^&*(),.?":{}|<>]/.test(value)],
    ];

    password?.addEventListener('input', () => {
        requirements.forEach(([element, isValid]) => {
            if (element) element.classList.toggle('requirement-met', isValid(password.value));
        });
        confirmPassword?.setCustomValidity('');
    });

    [['togglePassword', password, 'eyeIconPassword'], ['toggleConfirm', confirmPassword, 'eyeIconConfirm']]
        .forEach(([buttonId, input, iconId]) => {
            const button = document.getElementById(buttonId);
            const icon = document.getElementById(iconId);
            button?.addEventListener('click', () => {
                if (!input || !icon) return;
                input.type = input.type === 'password' ? 'text' : 'password';
                icon.classList.toggle('fa-eye');
                icon.classList.toggle('fa-eye-slash');
            });
        });

    form?.addEventListener('submit', event => {
        if (password && confirmPassword && password.value !== confirmPassword.value) {
            event.preventDefault();
            confirmPassword.setCustomValidity('Las contraseñas no coinciden.');
            confirmPassword.reportValidity();
        }
    });
});
