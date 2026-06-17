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

document.addEventListener('DOMContentLoaded', () => {
    const conversationsData = document.getElementById('conversations-data');
    const conversations = conversationsData ? JSON.parse(conversationsData.textContent) : [];

    const conversationList = document.getElementById('conversationList');
    const threadMessages = document.getElementById('threadMessages');
    const emptyState = document.getElementById('emptyState');
    const chatThread = document.getElementById('chatThread');
    const title = document.getElementById('activeConversationTitle');
    const subtitle = document.getElementById('activeConversationSubtitle');
    const clientName = document.getElementById('threadClientName');
    const clientCedula = document.getElementById('threadClientCedula');

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

        emptyState.hidden = true;
        chatThread.hidden = false;
        renderMessages(conversation);
    }

    if (!conversations.length) {
        conversationList.innerHTML = '';
        emptyState.hidden = false;
        chatThread.hidden = true;
        return;
    }

    conversationList.innerHTML = conversations.map((conversation, index) => `
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
    `).join('');

    conversationList.querySelectorAll('.conversation-item').forEach((item) => {
        item.addEventListener('click', () => setActiveConversation(item.dataset.conversationKey));
    });

    setActiveConversation(conversations[0].conversation_key);
});
