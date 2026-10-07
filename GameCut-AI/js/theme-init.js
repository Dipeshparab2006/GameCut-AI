(function () {
    try {
        var theme = 'system';
        var accent = '#7C3AED';
        var fontSize = 'comfortable';
        var compact = '0';
        try {
            theme = localStorage.getItem('gamecut-theme') || 'system';
            accent = localStorage.getItem('gamecut-accent') || '#7C3AED';
            fontSize = localStorage.getItem('gamecut-font') || 'comfortable';
            compact = localStorage.getItem('gamecut-compact') || '0';
        } catch (e) {
            // localStorage unavailable
        }
        var systemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        var resolved = theme === 'system' ? (systemDark ? 'dark' : 'light') : theme;
        document.documentElement.dataset.theme = resolved;
        document.documentElement.dataset.themeChoice = theme;
        document.documentElement.dataset.fontSize = fontSize;
        if (compact === '1') {
            document.documentElement.dataset.compactMode = 'true';
        }
        document.documentElement.style.setProperty('--primary', accent);
    } catch (e) {
        // Fallback: set light theme if anything fails
        document.documentElement.dataset.theme = 'light';
        document.documentElement.dataset.themeChoice = 'light';
    }
})();