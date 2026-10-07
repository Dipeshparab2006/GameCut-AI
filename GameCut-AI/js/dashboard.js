document.addEventListener('DOMContentLoaded', () => {
    // Number Counter Animation
    const counters = document.querySelectorAll('.counter');
    const speed = 200; // lower is faster

    counters.forEach(counter => {
        const updateCount = () => {
            const target = +counter.getAttribute('data-target');
            const count = +counter.innerText;
            const inc = target / speed;

            if (count < target) {
                counter.innerText = Math.ceil(count + inc);
                setTimeout(updateCount, 10);
            } else {
                counter.innerText = target;
            }
        };

        // Trigger animation
        updateCount();
    });
});
