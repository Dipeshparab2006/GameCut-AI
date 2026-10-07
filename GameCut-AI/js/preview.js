document.addEventListener('DOMContentLoaded', async () => {
    const toast = document.getElementById('exportToast');
    const downloadButtons = [
        document.getElementById('downloadBtn'),
        document.getElementById('downloadBtnHero')
    ].filter(Boolean);

    window.showToast = function(title, message) {
        if (!toast) return;
        if (title && message) {
            toast.querySelector('h4').textContent = title;
            toast.querySelector('p').textContent = message;
        }
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 5000);
    }

    window.copyToClipboard = function(textToCopy) {
        navigator.clipboard.writeText(textToCopy).then(() => {
            window.showToast('Copied to clipboard', 'Text has been copied successfully.');
        }).catch(err => {
            console.error('Failed to copy: ', err);
            window.showToast('Error', 'Failed to copy text.');
        });
    }

    downloadButtons.forEach(button => {
        button.addEventListener('click', async () => {
            const downloadUrl = button.dataset.downloadUrl;
            if (!downloadUrl) {
                window.showToast('Not ready yet', 'No generated video is available for download.');
                return;
            }

            window.showToast('Download started', 'Your AI-generated short is downloading.');
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = 'gamecut-highlight.mp4';
            document.body.appendChild(link);
            link.click();
            link.remove();
            
        });
    });
    
    // Subtle celebration effect on load
    setTimeout(() => {
        if(typeof confetti !== 'undefined') {
            confetti({
                particleCount: 100,
                spread: 70,
                origin: { y: 0.6 },
                colors: ['#7C3AED', '#3B82F6', '#ffffff']
            });
        }
    }, 500);
});
