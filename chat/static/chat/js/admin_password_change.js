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

    function setRequirementState(element, met) {
        if (!element) return;
        element.classList.toggle('requirement-met', met);
        const icon = element.querySelector('i');
        if (icon) {
            icon.classList.toggle('fa-circle', !met);
            icon.classList.toggle('fa-circle-check', met);
        }
    }

    function updatePasswordMatch() {
        const matchRequirement = document.getElementById('adminReqMatch');
        const met = Boolean(newPassword?.value && confirmPassword?.value)
            && newPassword.value === confirmPassword.value;
        setRequirementState(matchRequirement, met);
    }

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

    function updatePasswordRequirements() {
        if (!newPassword) return;
        requirements.forEach(([element, isValid]) => {
            setRequirementState(element, isValid(newPassword.value));
        });
        confirmPassword?.setCustomValidity('');
        updatePasswordMatch();
    }

    newPassword?.addEventListener('input', updatePasswordRequirements);
    newPassword?.addEventListener('change', updatePasswordRequirements);
    const updateConfirmation = () => {
        confirmPassword?.setCustomValidity('');
        updatePasswordMatch();
    };
    confirmPassword?.addEventListener('input', updateConfirmation);
    confirmPassword?.addEventListener('change', updateConfirmation);

    form?.addEventListener('submit', event => {
        if (newPassword && confirmPassword && newPassword.value !== confirmPassword.value) {
            event.preventDefault();
            confirmPassword.setCustomValidity('Las contraseñas no coinciden.');
            confirmPassword.reportValidity();
        }
    });
});
