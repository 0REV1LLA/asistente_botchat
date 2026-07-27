function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function renderMessage(text, sender, time = '') {
    const messages = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = `message ${sender}`;
    div.innerHTML = `
        <div class="text">${escapeHtml(text).replace(/\n/g, '<br>')}</div>
        ${time ? `<span class="msg-time">${escapeHtml(time)}</span>` : ''}
    `;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    updateScrollButton();
}

function loadHistory() {
    const historyElement = document.getElementById('chat-history-data');
    const messages = document.getElementById('messages');
    messages.innerHTML = '';

    if (!historyElement) {
        return;
    }

    const history = JSON.parse(historyElement.textContent || '[]');
    history.forEach((message) => {
        renderMessage(message.text, message.sender === 'client' ? 'user' : 'bot', message.time || '');
    });
    scrollToBottom(false);
}

function scrollToBottom(smooth = true) {
    const messages = document.getElementById('messages');
    if (!messages) {
        return;
    }

    messages.scrollTo({
        top: messages.scrollHeight,
        behavior: smooth ? 'smooth' : 'auto',
    });
    updateScrollButton();
}

function updateScrollButton() {
    const messages = document.getElementById('messages');
    const button = document.getElementById('scrollToBottomBtn');
    if (!messages || !button) {
        return;
    }

    const distanceFromBottom = messages.scrollHeight - messages.scrollTop - messages.clientHeight;
    button.dataset.atBottom = distanceFromBottom < 120 ? 'true' : 'false';
}

function setupConfirmDialog() {
    const overlay = document.getElementById('confirmOverlay');
    if (!overlay) {
        return null;
    }

    const title = overlay.querySelector('#confirmTitle');
    const message = overlay.querySelector('#confirmMessage');
    const cancelButton = overlay.querySelector('[data-confirm-cancel]');
    const acceptButton = overlay.querySelector('[data-confirm-accept]');
    let activeResolver = null;

    const closeDialog = (result) => {
        overlay.hidden = true;
        overlay.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('confirm-open');
        if (activeResolver) {
            activeResolver(result);
            activeResolver = null;
        }
    };

    cancelButton.addEventListener('click', () => closeDialog(false));
    acceptButton.addEventListener('click', () => closeDialog(true));
    overlay.addEventListener('click', (event) => {
        if (event.target === overlay) {
            closeDialog(false);
        }
    });

    document.addEventListener('keydown', (event) => {
        if (!overlay.hidden && event.key === 'Escape') {
            closeDialog(false);
        }
    });

    return ({ titleText, messageText, acceptText }) => {
        title.textContent = titleText;
        message.textContent = messageText;
        acceptButton.textContent = acceptText;
        overlay.hidden = false;
        overlay.setAttribute('aria-hidden', 'false');
        document.body.classList.add('confirm-open');

        return new Promise((resolve) => {
            activeResolver = resolve;
        });
    };
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    if (!input || input.disabled) {
        return;
    }
    const message = input.value.trim();
    if (!message) return;

    renderMessage(message, 'user');
    input.value = '';
    scrollToBottom();

    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing';
    typingDiv.innerHTML = '<span></span><span></span><span></span>';
    const messagesDiv = document.getElementById('messages');
    messagesDiv.appendChild(typingDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    updateScrollButton();

    try {
        const response = await fetch('/chat/enviar/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ mensaje: message })
        });

        const data = await response.json();
        typingDiv.remove();

        if (data.success) {
            renderMessage(data.respuesta, 'bot');
        } else if (data.blocked) {
            renderMessage('Usuario bloqueado', 'bot');
        } else {
            renderMessage('Error: ' + (data.error || 'Error desconocido'), 'bot');
        }
    } catch (error) {
        typingDiv.remove();
        console.error('Error:', error);
        renderMessage('Error de conexión: ' + error.message, 'bot');
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function initChat() {
    loadHistory();
    const input = document.getElementById('messageInput');
    const scrollButton = document.getElementById('scrollToBottomBtn');
    const logoutLink = document.querySelector('.js-logout-link');
    const confirmDialog = setupConfirmDialog();

    // ============================================
    // TOGGLE COMANDOS EN MÓVILES (NUEVO)
    // ============================================
    const toggleBtn = document.getElementById('toggleCommandsBtn');
    const commandPanel = document.querySelector('.command-panel');

    if (toggleBtn && commandPanel) {
        toggleBtn.addEventListener('click', function() {
            const isOpen = commandPanel.classList.toggle('open');
            toggleBtn.setAttribute('aria-expanded', isOpen);
            toggleBtn.innerHTML = isOpen
                ? '<i class="fa-solid fa-xmark"></i> Cerrar comandos'
                : '<i class="fa-solid fa-bars"></i> Comandos rápidos';
        });
    }

    if (input) {
        input.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') sendMessage();
        });
    }

    if (logoutLink) {
        logoutLink.addEventListener('click', (event) => {
            if (!confirmDialog) {
                return;
            }

            event.preventDefault();
            confirmDialog({
                titleText: 'Cerrar sesión',
                messageText: '¿Seguro que deseas cerrar sesión?',
                acceptText: 'Cerrar sesión',
            }).then((confirmed) => {
                if (confirmed) {
                    window.location.href = logoutLink.href;
                }
            });
        });
    }

    if (scrollButton) {
        scrollButton.addEventListener('click', () => scrollToBottom());
    }

    const messages = document.getElementById('messages');
    if (messages) {
        messages.addEventListener('scroll', updateScrollButton);
        updateScrollButton();
    }

    window.addEventListener('scroll', updateScrollButton, { passive: true });
    window.addEventListener('resize', updateScrollButton);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initChat);
} else {
    initChat();
}