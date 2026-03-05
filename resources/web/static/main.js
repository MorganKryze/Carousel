/* main.js — loaded globally via base.html */

function postJSON(url, body) {
    return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    }).then(function(r) { return r.json(); });
}

function updatePendingCount(n) {
    var banner = document.getElementById('unsaved-banner');
    var count = document.getElementById('unsaved-count');
    if (!banner) return;
    count.textContent = n;
    banner.style.display = n > 0 ? 'flex' : 'none';

    // Update body class for CSS spacing
    if (n > 0) {
        document.body.classList.add('has-banner');
    } else {
        document.body.classList.remove('has-banner');
    }
}

// Discard button in banner
document.getElementById('banner-discard')
    ?.addEventListener('click', function() {
        if (!confirm('Discard all unsaved changes?')) return;
        postJSON('/api/discard-changes', {}).then(function(d) {
            updatePendingCount(d.pending_count);
        });
    });

// Set initial banner class
(function() {
    var banner = document.getElementById('unsaved-banner');
    if (banner && banner.style.display !== 'none') {
        document.body.classList.add('has-banner');
    }
})();

/**
 * Two-phase reconnect after a server restart.
 * Phase 1: wait for the server to go DOWN (first failed request).
 * Phase 2: wait for the server to come back UP, then redirect.
 * This avoids a race where the first poll fires before the process
 * has actually restarted, causing a redirect into a dying server.
 */
function waitForRestart(redirectUrl) {
    var MAX_TRIES = 60;
    var downDetected = false;
    var tries = 0;
    var timer = setInterval(function() {
        tries++;
        fetch('/', { method: 'HEAD', cache: 'no-store' })
            .then(function() {
                if (downDetected) {
                    clearInterval(timer);
                    window.location.href = redirectUrl;
                }
                // else: server still up — wait for it to go down first
            })
            .catch(function() {
                downDetected = true;  // phase 1 complete; now watch for it to come back
            });
        if (tries >= MAX_TRIES) {
            clearInterval(timer);
        }
    }, 1000);
}
