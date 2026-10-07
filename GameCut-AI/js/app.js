document.addEventListener('DOMContentLoaded', () => {
    const themeChoice = (function () {
        try {
            return localStorage.getItem('gamecut-theme') || 'system';
        } catch (e) {
            return 'system';
        }
    })();
    const systemQuery = window.matchMedia('(prefers-color-scheme: dark)');

    function resolveTheme(choice) {
        return choice === 'system' ? (systemQuery.matches ? 'dark' : 'light') : choice;
    }

    function setTheme(choice) {
        try {
            var resolved = resolveTheme(choice);
            try {
                localStorage.setItem('gamecut-theme', choice);
            } catch (e) {
                // localStorage unavailable
            }
            document.documentElement.dataset.theme = resolved;
            document.documentElement.dataset.themeChoice = choice;
            document.querySelectorAll('[data-theme-value]').forEach(function (button) {
                button.classList.toggle('active', button.dataset.themeValue === choice);
            });
            document.querySelectorAll('[data-theme-select]').forEach(function (select) {
                select.value = choice;
            });
            // Update hidden theme input if present (settings.php)
            var themeInput = document.getElementById('themeInput');
            if (themeInput) {
                themeInput.value = choice;
            }
        } catch (e) {
            // Silently fail - theme is non-critical
        }
    }

    function icon(name) {
        var icons = {
            sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"></path></svg>',
            moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A8.5 8.5 0 1 1 11.2 3 6.6 6.6 0 0 0 21 12.8z"></path></svg>',
            search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path></svg>',
            bell: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>'
        };
        return icons[name] || '';
    }

    function ensureThemeToggle() {
        var targets = document.querySelectorAll('.nav-actions, .topbar-actions');
        targets.forEach(function (target) {
            if (target.querySelector('.theme-toggle')) return;
            var button = document.createElement('button');
            button.className = 'theme-toggle';
            button.type = 'button';
            button.setAttribute('aria-label', 'Toggle theme');
            button.innerHTML = '<span class="theme-toggle-track"><span class="theme-toggle-thumb">' + icon('sun') + icon('moon') + '</span></span>';
            button.addEventListener('click', function () {
                try {
                    var current = (function () {
                        try {
                            return localStorage.getItem('gamecut-theme') || 'system';
                        } catch (e) {
                            return 'system';
                        }
                    })();
                    setTheme(resolveTheme(current) === 'dark' ? 'light' : 'dark');
                    showToast('Theme updated', 'Switched to ' + document.documentElement.dataset.theme + ' mode.');
                } catch (e) {
                    // Silently fail
                }
            });
            target.prepend(button);
        });
    }

    function ensureMenus() {
        document.querySelectorAll('.profile-dropdown').forEach(function (profile) {
            if (profile.querySelector('.profile-menu')) return;
            var menu = document.createElement('div');
            menu.className = 'profile-menu';
            menu.innerHTML = '\
                <a href="profile.php">Profile</a>\
                <a href="settings.php">Settings</a>\
                <a href="php/logout.php">Logout</a>\
            ';
            profile.appendChild(menu);
            profile.setAttribute('tabindex', '0');
            profile.addEventListener('click', function (event) {
                event.stopPropagation();
                profile.classList.toggle('open');
            });
        });

        document.addEventListener('click', function () {
            document.querySelectorAll('.profile-dropdown.open').forEach(function (item) { item.classList.remove('open'); });
        });
    }

    function ensureCommandPalette() {
        if (document.getElementById('commandPalette')) return;
        var palette = document.createElement('div');
        palette.className = 'command-palette';
        palette.id = 'commandPalette';
        palette.innerHTML = '\
            <div class="command-dialog">\
                <div class="command-input-wrap">' + icon('search') + '<input id="commandInput" type="text" placeholder="Search pages, AI shorts, actions..."></div>\
                <div class="command-list">\
                    <a href="upload.php"><span>Generate new AI short</span><kbd>G</kbd></a>\
                    <a href="dashboard.php"><span>Open dashboard</span><kbd>D</kbd></a>\
                    <a href="projects.php"><span>Browse AI shorts</span><kbd>P</kbd></a>\
                    <a href="settings.php"><span>Open settings</span><kbd>S</kbd></a>\
                    <button type="button" data-command-theme><span>Toggle theme</span><kbd>T</kbd></button>\
                </div>\
            </div>';
        document.body.appendChild(palette);
        palette.addEventListener('click', function (event) {
            if (event.target === palette) palette.classList.remove('open');
        });
        var cmdThemeBtn = palette.querySelector('[data-command-theme]');
        if (cmdThemeBtn) {
            cmdThemeBtn.addEventListener('click', function () {
                try {
                    var current = (function () {
                        try {
                            return localStorage.getItem('gamecut-theme') || 'system';
                        } catch (e) {
                            return 'system';
                        }
                    })();
                    setTheme(resolveTheme(current) === 'dark' ? 'light' : 'dark');
                    palette.classList.remove('open');
                } catch (e) {
                    // Silently fail
                }
            });
        }
    }

    function openCommandPalette() {
        ensureCommandPalette();
        var palette = document.getElementById('commandPalette');
        if (palette) {
            palette.classList.add('open');
            var input = palette.querySelector('input');
            if (input) input.focus();
        }
    }

    function ensureToasts() {
        if (!document.querySelector('.toast-stack')) {
            var stack = document.createElement('div');
            stack.className = 'toast-stack';
            document.body.appendChild(stack);
        }
    }

    window.showToast = function (title, message) {
        if (typeof message === 'undefined') message = '';
        try {
            ensureToasts();
            var toast = document.createElement('div');
            toast.className = 'app-toast';
            toast.innerHTML = '<strong>' + title + '</strong>' + (message ? '<span>' + message + '</span>' : '');
            var stack = document.querySelector('.toast-stack');
            if (!stack) return;
            stack.appendChild(toast);
            requestAnimationFrame(function () { toast.classList.add('show'); });
            setTimeout(function () {
                toast.classList.remove('show');
                setTimeout(function () { if (toast.parentNode) toast.remove(); }, 250);
            }, 3200);
        } catch (e) {
            // Toast is non-critical
        }
    };

    function formatBytes(bytes) {
        if (!Number.isFinite(bytes) || bytes <= 0) return '0 MB';
        var units = ['B', 'KB', 'MB', 'GB', 'TB'];
        var value = bytes;
        var unit = 0;
        while (value >= 1024 && unit < units.length - 1) {
            value /= 1024;
            unit++;
        }
        return value.toFixed(unit < 2 ? 0 : 1) + ' ' + units[unit];
    }

    async function updateStorageUi() {
        var usage = 0;
        var quota = 0;
        var percent = 0;
        var supported = false;

        // Try StorageManager first
        if (typeof window.StorageManager !== 'undefined' && window.StorageManager !== null) {
            try {
                var storageUsage = await StorageManager.getStorageUsage();
                if (storageUsage) {
                    usage = storageUsage.usage;
                    quota = storageUsage.quota;
                    percent = storageUsage.percent;
                    supported = true;
                }
            } catch (error) {
                console.error('StorageManager error:', error);
            }
        }

        // Fallback to native API
        if (!supported && navigator.storage && navigator.storage.estimate) {
            try {
                var estimate = await navigator.storage.estimate();
                usage = (estimate && estimate.usage) || 0;
                quota = (estimate && estimate.quota) || 0;
                percent = quota ? Math.min(100, Math.round((usage / quota) * 100)) : 0;
                supported = true;
            } catch (error) {
                console.error('Storage estimate error:', error);
            }
        }

        document.querySelectorAll('[data-storage-used]').forEach(function (item) {
            item.textContent = supported ? formatBytes(usage) : 'Browser managed';
        });
        document.querySelectorAll('[data-storage-quota]').forEach(function (item) {
            item.textContent = supported ? formatBytes(quota) : 'Unavailable';
        });
        document.querySelectorAll('[data-storage-bar]').forEach(function (item) {
            item.style.width = (supported ? Math.max(percent, 8) : 30) + '%';
        });
        document.querySelectorAll('[data-storage-status]').forEach(function (item) {
            item.textContent = supported ? percent + '% of available browser storage used' : 'Storage estimate is not supported in this browser';
        });
    }

    async function refreshPermissionUi() {
        var notificationStatus = document.querySelectorAll('[data-permission-status="notifications"]');
        var storageStatus = document.querySelectorAll('[data-permission-status="storage"]');
        var fileStatus = document.querySelectorAll('[data-permission-status="files"]');
        var persistentStatus = document.querySelectorAll('[data-permission-status="persistentStorage"]');

        // Notification permission
        notificationStatus.forEach(function (item) {
            try {
                item.textContent = 'Notification' in window ? Notification.permission : 'unsupported';
            } catch (e) {
                item.textContent = 'unsupported';
            }
        });

        // Storage and persistent storage permissions
        if (typeof window.StorageManager !== 'undefined' && window.StorageManager !== null) {
            try {
                var permissions = await StorageManager.getAllPermissionStatuses();

                storageStatus.forEach(function (item) {
                    item.textContent = (permissions && permissions.storage) || 'available';
                });

                persistentStatus.forEach(function (item) {
                    item.textContent = (permissions && permissions.persistentStorage) || 'available';
                });

                fileStatus.forEach(function (item) {
                    item.textContent = (permissions && permissions.files === 'granted') ? 'granted' :
                        (permissions && permissions.files === 'not_requested') ? 'granted when you choose a video' :
                            (permissions && permissions.files) || 'granted when you choose a video';
                });
            } catch (error) {
                console.error('Permission check failed:', error);
                storageStatus.forEach(function (item) { item.textContent = 'error'; });
                persistentStatus.forEach(function (item) { item.textContent = 'error'; });
            }
        } else {
            // Fallback to native API
            if (navigator.storage && navigator.storage.persisted) {
                try {
                    var persisted = await navigator.storage.persisted();
                    storageStatus.forEach(function (item) {
                        item.textContent = persisted ? 'granted' : 'available';
                    });
                } catch (e) {
                    storageStatus.forEach(function (item) { item.textContent = 'available'; });
                }
            } else {
                storageStatus.forEach(function (item) { item.textContent = 'unsupported'; });
            }

            fileStatus.forEach(function (item) {
                item.textContent = 'granted when you choose a video';
            });
        }
    }

    async function requestNotifications() {
        if (!('Notification' in window)) {
            showToast('Notifications unavailable', 'This browser does not support notification permission.');
            return;
        }
        try {
            var permission = await Notification.requestPermission();
            showToast(
                permission === 'granted' ? 'Notifications enabled' : 'Notifications not enabled',
                permission === 'granted' ? 'We can alert you when AI videos finish.' : 'You can enable this later from browser settings.'
            );
            refreshPermissionUi();
        } catch (error) {
            showToast('Notification request failed', error.message || 'Could not request notification permission.');
        }
    }

    async function requestPersistentStorage() {
        if (typeof window.StorageManager !== 'undefined' && window.StorageManager !== null) {
            try {
                var result = await StorageManager.requestPersistentStorage();
                showToast(
                    result && result.granted ? 'Storage protected' : 'Storage remains browser managed',
                    result && result.granted ? 'Temporary render metadata is less likely to be cleared automatically.' :
                        (result && result.reason === 'not_supported') ? 'This browser does not support persistent storage.' :
                            'Your browser decides when cached data is cleared.'
                );
            } catch (error) {
                showToast('Storage permission error', error.message || 'Unknown error');
            }
        } else if (navigator.storage && navigator.storage.persist) {
            try {
                var granted = await navigator.storage.persist();
                showToast(
                    granted ? 'Storage protected' : 'Storage remains browser managed',
                    granted ? 'Temporary render metadata is less likely to be cleared automatically.' : 'Your browser decides when cached data is cleared.'
                );
            } catch (error) {
                showToast('Storage permission error', error.message || 'Unknown error');
            }
        } else {
            showToast('Storage permission unavailable', 'This browser does not support persistent storage requests.');
        }
        refreshPermissionUi();
        updateStorageUi();
    }

    function enhanceActions() {
        document.querySelectorAll('[data-toast]').forEach(function (item) {
            item.addEventListener('click', function () { showToast(item.dataset.toast || 'Action complete'); });
        });
        document.querySelectorAll('[data-contact-form]').forEach(function (form) {
            form.addEventListener('submit', function (event) {
                event.preventDefault();
                showToast('Message sent', 'Thanks. The GameCut team will reply soon.');
                form.reset();
            });
        });
        document.querySelectorAll('[data-request-notifications]').forEach(function (button) {
            button.addEventListener('click', requestNotifications);
        });
        document.querySelectorAll('[data-request-storage]').forEach(function (button) {
            button.addEventListener('click', requestPersistentStorage);
        });
        document.querySelectorAll('[data-refresh-storage]').forEach(function (button) {
            button.addEventListener('click', async function () {
                await updateStorageUi();
                await refreshPermissionUi();
                showToast('Storage refreshed', 'Latest browser storage estimate loaded.');
            });
        });
        document.querySelectorAll('.search-bar input').forEach(function (input) {
            input.addEventListener('focus', openCommandPalette);
        });
        document.querySelectorAll('.icon-btn').forEach(function (button) {
            if (button.querySelector('.notification-badge') && !button.dataset.enhancedBell) {
                button.dataset.enhancedBell = 'true';
                button.addEventListener('click', function () { showToast('Notifications', '3 AI videos are ready for review.'); });
            }
        });
    }

    document.addEventListener('keydown', function (event) {
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
            event.preventDefault();
            openCommandPalette();
        }
        if (event.key === 'Escape') {
            var palette = document.getElementById('commandPalette');
            if (palette) palette.classList.remove('open');
        }
    });

    if (systemQuery && typeof systemQuery.addEventListener === 'function') {
        systemQuery.addEventListener('change', function () {
            try {
                var current = (function () {
                    try {
                        return localStorage.getItem('gamecut-theme') || 'system';
                    } catch (e) {
                        return 'system';
                    }
                })();
                if (current === 'system') setTheme('system');
            } catch (e) {
                // Silently fail
            }
        });
    }

    document.querySelectorAll('[data-theme-value]').forEach(function (button) {
        button.addEventListener('click', function () { setTheme(button.dataset.themeValue); });
    });
    document.querySelectorAll('[data-theme-select]').forEach(function (select) {
        select.addEventListener('change', function () { setTheme(select.value); });
    });

    setTheme(themeChoice);
    ensureThemeToggle();
    ensureMenus();
    ensureCommandPalette();
    ensureToasts();
    enhanceActions();

    // Initialize storage manager if available (only if not already initialized)
    const initializeAppStorage = async () => {
        if (typeof window.StorageManager !== 'undefined' && window.StorageManager !== null) {
            try {
                await StorageManager.initialize();
            } catch (error) {
                console.error('StorageManager initialization failed:', error);
            }
        }
        updateStorageUi();
        refreshPermissionUi();
    };

    initializeAppStorage();
});