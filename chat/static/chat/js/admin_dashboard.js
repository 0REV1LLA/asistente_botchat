function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatMessage(text) {
    return escapeHtml(text).replace(/\n/g, '<br>');
}

function bubbleClassFor(message) {
    return message.bubble_class || (message.sender === 'bot' ? 'superadmin' : 'client');
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

// ============================================
// MODAL DE ÉXITO - RESPONSIVE Y ESTILIZADO
// ============================================
function showSuccessModal(message, callback) {
    const overlay = document.getElementById('successOverlay');
    if (!overlay) {
        alert(message);
        if (callback) callback();
        return;
    }

    const title = overlay.querySelector('#successTitle');
    const messageElement = overlay.querySelector('#successMessage');
    const closeButton = overlay.querySelector('[data-success-close]');

    title.textContent = '¡Éxito!';
    messageElement.textContent = message;

    overlay.hidden = false;
    overlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('success-open');

    const closeModal = () => {
        overlay.hidden = true;
        overlay.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('success-open');
        if (callback) callback();
    };

    const newCloseButton = closeButton.cloneNode(true);
    closeButton.parentNode.replaceChild(newCloseButton, closeButton);

    newCloseButton.addEventListener('click', closeModal);
    overlay.addEventListener('click', (event) => {
        if (event.target === overlay) {
            closeModal();
        }
    });

    document.addEventListener('keydown', function handler(event) {
        if (!overlay.hidden && event.key === 'Escape') {
            closeModal();
            document.removeEventListener('keydown', handler);
        }
    });
}

// Función para obtener el CSRF token
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

// ============================================
// MENÚ LATERAL PARA MÓVILES - SUPERADMIN
// ============================================
function initSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const toggleBtn = document.getElementById('sidebarToggleBtn');
    const overlay = document.getElementById('sidebarOverlay');
    const contentPanel = document.querySelector('.content-panel');

    function openSidebar() {
        if (sidebar) {
            sidebar.classList.add('open');
            if (overlay) overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
            if (toggleBtn) {
                toggleBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
                toggleBtn.setAttribute('aria-label', 'Cerrar lista de chats');
            }
            if (contentPanel) {
                contentPanel.classList.add('shifted');
            }
        }
    }

    function closeSidebar() {
        if (sidebar) {
            sidebar.classList.remove('open');
            if (overlay) overlay.classList.remove('active');
            document.body.style.overflow = '';
            if (toggleBtn) {
                toggleBtn.innerHTML = '<i class="fa-solid fa-bars"></i>';
                toggleBtn.setAttribute('aria-label', 'Abrir lista de chats');
            }
            if (contentPanel) {
                contentPanel.classList.remove('shifted');
            }
        }
    }

    if (toggleBtn) {
        toggleBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            const isOpen = sidebar && sidebar.classList.contains('open');
            if (isOpen) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }

    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }

    document.addEventListener('click', function(e) {
        const conversationItem = e.target.closest('.conversation-item');
        if (conversationItem && window.innerWidth <= 480) {
            setTimeout(closeSidebar, 300);
        }
    });

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('open')) {
            closeSidebar();
        }
    });

    window.addEventListener('resize', function() {
        if (window.innerWidth > 480 && sidebar && sidebar.classList.contains('open')) {
            closeSidebar();
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const conversationsData = document.getElementById('conversations-data');
    const conversations = conversationsData ? JSON.parse(conversationsData.textContent) : [];

    const conversationList = document.getElementById('conversationList');
    const threadMessages = document.getElementById('threadMessages');
    const emptyState = document.getElementById('emptyState');
    const chatThread = document.getElementById('chatThread');
    const title = document.getElementById('activeConversationTitle');
    const threadMeta = document.querySelector('.thread-meta');
    const subtitle = document.getElementById('activeConversationSubtitle');
    const clientName = document.getElementById('threadClientName');
    const clientCedula = document.getElementById('threadClientCedula');
    const scrollButton = document.getElementById('scrollToBottomBtn');
    const confirmDialog = setupConfirmDialog();

    // Inicializar menú lateral
    initSidebar();

    function scrollThreadToBottom(smooth = true) {
        if (!threadMessages) {
            return;
        }

        threadMessages.scrollTo({
            top: threadMessages.scrollHeight,
            behavior: smooth ? 'smooth' : 'auto',
        });
    }

    function renderMessages(conversation) {
        threadMessages.innerHTML = '';

        conversation.messages.forEach((message) => {
            const bubble = document.createElement('article');
            bubble.className = `message ${bubbleClassFor(message)}`;

            bubble.innerHTML = `
                <div class="message-label">${escapeHtml(message.sender_label || '')}</div>
                <div class="message-text">${formatMessage(message.text)}</div>
                <span class="msg-time">${escapeHtml(message.time)}</span>
            `;

            threadMessages.appendChild(bubble);
        });

        threadMessages.scrollTop = threadMessages.scrollHeight;
    }

// chat/static/chat/js/admin_dashboard.js
function setActiveConversation(conversationKey) {
    const conversation = conversations.find((item) => item.conversation_key === conversationKey);
    if (!conversation) {
        return;
    }

    document.querySelectorAll('.conversation-item').forEach((item) => {
        item.classList.toggle('active', item.dataset.conversationKey === conversationKey);
    });

    title.textContent = conversation.client_name;
    subtitle.textContent = `Último movimiento a las ${conversation.last_time}.`;
    clientName.textContent = conversation.client_name;
    clientCedula.textContent = conversation.cedula;

    const patologiaElement = document.getElementById('threadClientPatologia');
    if (patologiaElement) {
        const patologiaMap = {
            'hipertension': 'Hipertensión',
            'diabetes': 'Diabetes',
            'oftalmologico': 'Oftalmológico',
            'pediatrico': 'Pediátrico',
            'ginecologico': 'Ginecológico',
            'otro': 'Otros'
        };
        patologiaElement.textContent = patologiaMap[conversation.patologia] || conversation.patologia || '-';
    }

    if (threadMeta) {
        const bloqueoBadge = document.getElementById('block-status-badge');
        if (bloqueoBadge) {
            bloqueoBadge.remove();
        }
        const badge = document.createElement('span');
        badge.id = 'block-status-badge';
        badge.className = conversation.bloqueado ? 'status-badge blocked' : 'status-badge active';
        badge.textContent = conversation.bloqueado ? 'Bloqueado' : 'Activo';
        threadMeta.appendChild(badge);
    }

    emptyState.hidden = true;
    chatThread.hidden = false;
    renderMessages(conversation);
    scrollThreadToBottom(false);
}

const logoutLink = document.querySelector('.js-logout-link');
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

if (!conversations.length) {
    conversationList.innerHTML = '';
    emptyState.hidden = false;
    chatThread.hidden = true;
    return;
}

    // ============================================
    // RENDERIZAR CONVERSACIONES CON BOTÓN BORRAR
    // ============================================
    conversationList.innerHTML = conversations.map((conversation, index) => {
        // 👇 ASEGURAR QUE TENGA UN ID VÁLIDO
        const clientId = conversation.cliente_id || 0;
        return `
        <div class="conversation-item-wrap">
            <button type="button" class="conversation-item ${index === 0 ? 'active' : ''}" data-conversation-key="${escapeHtml(conversation.conversation_key)}">
                <div class="avatar">${escapeHtml(conversation.avatar || conversation.initials || 'CL')}</div>
                <div>
                    <div class="conversation-title">
                        <h3>${escapeHtml(conversation.client_name)}</h3>
                        <span class="conversation-time">${escapeHtml(conversation.last_time)}</span>
                    </div>
                    <p class="conversation-preview">${escapeHtml(conversation.last_message)}</p>
                </div>
            </button>
            <div style="display: flex; gap: 4px; align-items: center; flex-shrink: 0;">
                <a class="block-toggle ${conversation.bloqueado ? 'blocked' : 'active'} js-block-toggle" href="/chat/bloquear/${clientId}/" data-client-id="${clientId}">
                    <i class="fa-solid ${conversation.bloqueado ? 'fa-unlock' : 'fa-lock'}"></i>
                </a>
                <a class="block-toggle delete-chat js-delete-chat" href="#" data-conversation-key="${escapeHtml(conversation.conversation_key)}" data-client-id="${clientId}" style="color: #b42318; background: #ffe7e7; border-color: rgba(180, 35, 24, 0.16);">
                    <i class="fa-solid fa-trash-can"></i>
                </a>
            </div>
        </div>
    `}).join('');

    // ============================================
    // EVENTO PARA BLOQUEAR/DESBLOQUEAR (CON VALIDACIÓN)
    // ============================================
    conversationList.querySelectorAll('.js-block-toggle').forEach((item) => {
        item.addEventListener('click', (event) => {
            // 👇 VALIDAR QUE EL CLIENTE_ID EXISTA
            const clientId = item.dataset.clientId;
            if (!clientId || clientId === '0' || clientId === '') {
                event.preventDefault();
                alert('❌ Error: No se puede bloquear este usuario (ID no válido).');
                return;
            }

            if (!confirmDialog) {
                return;
            }

            event.preventDefault();
            const isBlocked = item.classList.contains('blocked');
            confirmDialog({
                titleText: isBlocked ? 'Desbloquear usuario' : 'Bloquear usuario',
                messageText: isBlocked ? '¿Seguro que deseas desbloquear este usuario?' : '¿Seguro que deseas bloquear este usuario?',
                acceptText: isBlocked ? 'Desbloquear' : 'Bloquear',
            }).then((confirmed) => {
                if (confirmed) {
                    window.location.href = item.href;
                }
            });
        });
    });

    // ============================================
    // EVENTO PARA BORRAR CHAT (CON MODAL DE ÉXITO)
    // ============================================
    conversationList.querySelectorAll('.js-delete-chat').forEach((item) => {
        item.addEventListener('click', (event) => {
            if (!confirmDialog) {
                return;
            }

            event.preventDefault();
            const conversationKey = item.dataset.conversationKey;
            const clientId = item.dataset.clientId;

            confirmDialog({
                titleText: 'Borrar conversación',
                messageText: '¿Seguro que deseas borrar esta conversación? El usuario regular seguirá viendo sus mensajes.',
                acceptText: 'Borrar',
            }).then((confirmed) => {
                if (confirmed) {
                    fetch('/chat/borrar-conversacion/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken')
                        },
                        body: JSON.stringify({
                            conversation_key: conversationKey,
                            cliente_id: clientId
                        })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            showSuccessModal('Se ha borrado el chat exitosamente', () => {
                                window.location.reload();
                            });
                        } else {
                            alert('❌ Error al borrar el chat: ' + data.error);
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('❌ Error al borrar el chat');
                    });
                }
            });
        });
    });

    // ============================================
    // SCROLL BOTTOM
    // ============================================
    if (scrollButton) {
        scrollButton.addEventListener('click', () => scrollThreadToBottom());
    }

    if (threadMessages) {
        threadMessages.addEventListener('scroll', () => {
            if (scrollButton) {
                const distanceFromBottom = threadMessages.scrollHeight - threadMessages.scrollTop - threadMessages.clientHeight;
                scrollButton.dataset.atBottom = distanceFromBottom < 120 ? 'true' : 'false';
            }
        });
    }

    // ============================================
    // SELECCIONAR CONVERSACIÓN
    // ============================================
    conversationList.querySelectorAll('.conversation-item').forEach((item) => {
        item.addEventListener('click', () => setActiveConversation(item.dataset.conversationKey));
    });

    setActiveConversation(conversations[0].conversation_key);
});