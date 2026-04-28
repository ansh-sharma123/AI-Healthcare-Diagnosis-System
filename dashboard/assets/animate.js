document.addEventListener("DOMContentLoaded", () => {
    // We use a small delay or Intersection Observer to trigger it.
    setTimeout(() => {
        const counters = document.querySelectorAll('.count-up-target');
        const duration = 2000; // ms

        counters.forEach(counter => {
            const target = +counter.getAttribute('data-target');
            const start = 0;
            let startTime = null;

            const step = (timestamp) => {
                if (!startTime) startTime = timestamp;
                const progress = Math.min((timestamp - startTime) / duration, 1);
                
                // Ease out quad
                const easeProgress = progress * (2 - progress);
                
                counter.innerText = Math.floor(easeProgress * (target - start) + start);
                
                if (progress < 1) {
                    window.requestAnimationFrame(step);
                } else {
                    counter.innerText = target;
                }
            };
            window.requestAnimationFrame(step);
        });
    }, 500); // 500ms delay to let the page render properly
});
