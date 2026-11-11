document.addEventListener('DOMContentLoaded', () => {
    const config = document.querySelector('[data-session-timeout]');
    const overlay = document.getElementById('sessionTimeoutOverlay');
    const keepAliveButton = document.getElementById('keepSessionActive');
    const countdown = document.getElementById('sessionCountdown');
    if (!config || !overlay || !keepAliveButton || !countdown) return;

    const warningMilliseconds = 8 * 60 * 1000;
    const heartbeatMilliseconds = 10 * 1000;
    const logoutUrl = config.dataset.logoutUrl;
    const renewUrl = config.dataset.renewUrl;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    const storedLastActivity = Number(config.dataset.lastActivity) * 1000;
    let lastActivity = Number.isFinite(storedLastActivity) && storedLastActivity > 0
        ? storedLastActivity
        : Date.now();
    let lastHeartbeatActivity = lastActivity;
    let warningTimer;
    let countdownTimer;
    let heartbeatTimer;
    let warningVisible = false;
    let heartbeatInFlight = false;

    function hideWarning() {
        overlay.hidden = true;
        overlay.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('confirm-open');
        warningVisible = false;
        window.clearInterval(countdownTimer);
    }

    function logout() {
        window.location.assign(`${logoutUrl}?expired=1`);
    }

    function showWarning() {
        warningVisible = true;
        overlay.hidden = false;
        overlay.setAttribute('aria-hidden', 'false');
        document.body.classList.add('confirm-open');
        let remainingSeconds = 30;
        countdown.textContent = String(remainingSeconds);
        countdownTimer = window.setInterval(() => {
            remainingSeconds -= 1;
            countdown.textContent = String(Math.max(remainingSeconds, 0));
            if (remainingSeconds <= 0) {
                window.clearInterval(countdownTimer);
                logout();
            }
        }, 1000);
    }

    function scheduleWarning() {
        window.clearTimeout(warningTimer);
        if (!warningVisible) {
            warningTimer = window.setTimeout(showWarning, Math.max(0, lastActivity + warningMilliseconds - Date.now()));
        }
    }

    function recordActivity() {
        if (warningVisible) return;
        lastActivity = Date.now();
        scheduleWarning();
    }

    async function renewSession() {
        keepAliveButton.disabled = true;
        try {
            const response = await fetch(renewUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: '{}',
                credentials: 'same-origin',
            });
            if (!response.ok) throw new Error('La sesión ya no está disponible.');
            hideWarning();
            recordActivity();
            lastHeartbeatActivity = lastActivity;
        } catch (error) {
            window.location.assign(`${logoutUrl}?expired=1`);
        } finally {
            keepAliveButton.disabled = false;
        }
    }

    async function sendHeartbeat() {
        if (warningVisible || heartbeatInFlight || lastActivity <= lastHeartbeatActivity) return;
        heartbeatInFlight = true;
        const activityAtRequest = lastActivity;
        try {
            const response = await fetch(renewUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: '{}',
                credentials: 'same-origin',
            });
            if (!response.ok) window.location.assign(`${logoutUrl}?expired=1`);
            else lastHeartbeatActivity = activityAtRequest;
        } catch (error) {
            console.error('No se pudo renovar la actividad de la sesión.', error);
        } finally {
            heartbeatInFlight = false;
        }
    }

    keepAliveButton.addEventListener('click', renewSession);
    ['pointerdown', 'keydown', 'scroll', 'touchstart'].forEach(eventName => {
        document.addEventListener(eventName, recordActivity, { passive: true });
    });
    window.addEventListener('mousemove', recordActivity, { passive: true });
    heartbeatTimer = window.setInterval(sendHeartbeat, heartbeatMilliseconds);
    scheduleWarning();

    window.addEventListener('pagehide', () => {
        window.clearInterval(heartbeatTimer);
        window.clearTimeout(warningTimer);
        window.clearInterval(countdownTimer);
    }, { once: true });
});
