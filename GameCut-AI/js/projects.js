document.querySelectorAll('.delete-project-btn').forEach(button => {
    button.addEventListener('click', async () => {
        const projectId = button.dataset.projectId;
        if (!projectId || !window.confirm('Delete this project and its generated files?')) return;
        button.disabled = true;
        try {
            const body = new URLSearchParams({project_id: projectId, csrf_token: button.dataset.csrf});
            const response = await fetch('api/delete_project.php', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'},
                body
            });
            const result = await response.json();
            // A stale card can remain in an already-open tab after the record
            // was deleted elsewhere. Treat 404 as success from the user's
            // point of view and remove that card from the current list.
            if (response.status === 404) {
                button.closest('.project-card')?.remove();
                window.showToast?.('Project removed', 'It was already deleted from the database.');
                return;
            }
            if (!response.ok || !result.ok) throw new Error(result.message || 'Delete failed');
            button.closest('.project-card')?.remove();
            window.showToast?.('Project deleted', response.status === 202
                ? 'The project was removed from your library and its files will be cleaned safely.'
                : 'The project and its files were removed.');
        } catch (error) {
            button.disabled = false;
            window.showToast?.('Delete failed', error.message);
        }
    });
});
