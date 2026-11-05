document.addEventListener("DOMContentLoaded", () => {
  const observerOptions = {
    root: null,
    rootMargin: "0px",
    threshold: 0.1,
  };

  const observer = new IntersectionObserver((entries, observerInstance) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observerInstance.unobserve(entry.target); // Se ejecuta una sola vez (viewport={{ once: true }})
      }
    });
  }, observerOptions);

  document.querySelectorAll(".scroll-reveal").forEach((el) => {
    observer.observe(el);
  });
});