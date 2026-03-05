/* review.js — loaded on the review page */

// Confirm & Restart
document.getElementById('confirm-restart-btn')
    ?.addEventListener('click', function() {
        var btn = this;
        btn.disabled = true;
        btn.textContent = 'Saving...';

        postJSON('/api/save-changes', {})
            .then(function(d) {
                if (d.status === 'success') {
                    document.getElementById('restart-overlay').style.display = 'flex';
                    waitForRestart('/catalog');
                } else {
                    document.getElementById('save-error').textContent = d.message;
                    document.getElementById('save-error').style.display = 'block';
                    btn.disabled = false;
                    btn.textContent = 'Confirm & Restart';
                }
            })
            .catch(function() {
                btn.disabled = false;
                btn.textContent = 'Confirm & Restart';
                document.getElementById('save-error').textContent = 'Request failed. Check your connection.';
                document.getElementById('save-error').style.display = 'block';
            });
    });

// Discard All
document.getElementById('discard-all-btn')
    ?.addEventListener('click', function() {
        if (!confirm('Discard all unsaved changes?')) return;
        postJSON('/api/discard-changes', {})
            .then(function() {
                window.location.href = '/catalog';
            });
    });
