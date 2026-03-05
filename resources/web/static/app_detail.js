/* app_detail.js — loaded on app detail and settings section pages */

// Stage field change on input change
document.querySelectorAll('[data-path]').forEach(function(input) {
    input.addEventListener('change', function() {
        var path = this.dataset.path;
        var value = this.value;

        // Type coercion
        if (value === 'true') value = true;
        if (value === 'false') value = false;
        if (this.type === 'number') value = Number(value);

        postJSON('/api/stage-change', { path: path, new_value: value })
            .then(function(d) {
                updatePendingCount(d.pending_count);
                // Yellow border if staged
                input.classList.toggle('staged', d.pending_count > 0);
            });
    });
});

// Toggle enable/disable button
document.getElementById('toggle-app-btn')
    ?.addEventListener('click', function() {
        var appKey = this.dataset.appKey;
        var btn = this;

        postJSON('/api/toggle-app', { app_key: appKey })
            .then(function(d) {
                updatePendingCount(d.pending_count);

                // Update badge UI
                var badge = document.getElementById('enabled-badge');
                if (badge) {
                    var newEnabled = d.new_enabled;
                    badge.dataset.enabled = String(newEnabled);
                    badge.textContent = newEnabled ? 'ENABLED' : 'DISABLED';
                    badge.className = newEnabled
                        ? 'badge badge-success'
                        : 'badge badge-muted';

                    // Update button
                    btn.textContent = newEnabled ? 'Disable' : 'Enable';
                    btn.className = newEnabled
                        ? 'btn btn-ghost'
                        : 'btn btn-success';
                }
            });
    });
