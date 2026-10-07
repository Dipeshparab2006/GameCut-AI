document.addEventListener('DOMContentLoaded', function() {
    try {
        document.documentElement.classList.add('motion-ready');
        var revealSelectors = [
            '.section-header',
            '.trust-pill',
            '.game-logo',
            '.feature-card',
            '.step',
            '.demo-box',
            '.demo-arrow',
            '.pricing-card',
            '.accordion-item',
            '#contact .contact-form-container',
            '.footer-brand',
            '.link-group'
        ];

        document.querySelectorAll(revealSelectors.join(',')).forEach(function(element, index) {
            if (!element.hasAttribute('data-animate')) {
                element.setAttribute('data-animate', '');
            }
            if (!element.style.getPropertyValue('--reveal-delay')) {
                element.style.setProperty('--reveal-delay', Math.min(index % 8, 7) * 70 + 'ms');
            }
        });

        if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            var animationObserver = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('is-visible');
                        animationObserver.unobserve(entry.target);
                    }
                });
            }, {
                threshold: 0.12,
                rootMargin: '0px 0px -48px 0px'
            });

            document.querySelectorAll('[data-animate]').forEach(function(element) {
                animationObserver.observe(element);
            });
        } else {
            document.querySelectorAll('[data-animate]').forEach(function(element) {
                element.classList.add('is-visible');
            });
        }
    } catch (e) {
        // Reveal motion is non-critical.
    }

    try {
        // 1. Mobile Menu Toggle
        var mobileMenuBtn = document.querySelector('.mobile-menu-btn');
        var mobileMenu = document.querySelector('.mobile-menu');
        
        if (mobileMenuBtn && mobileMenu) {
            mobileMenuBtn.addEventListener('click', function() {
                try {
                    mobileMenu.classList.toggle('active');
                    // Change icon
                    var svg = mobileMenuBtn.querySelector('svg');
                    if (svg) {
                        if (mobileMenu.classList.contains('active')) {
                            svg.innerHTML = '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>';
                        } else {
                            svg.innerHTML = '<line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line>';
                        }
                    }
                } catch (e) {
                    // Non-critical UI error
                }
            });

            // Close menu when clicking a link
            var mobileLinks = mobileMenu.querySelectorAll('a');
            mobileLinks.forEach(function(link) {
                link.addEventListener('click', function() {
                    try {
                        mobileMenu.classList.remove('active');
                        var svg = mobileMenuBtn.querySelector('svg');
                        if (svg) {
                            svg.innerHTML = '<line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line>';
                        }
                    } catch (e) {
                        // Non-critical
                    }
                });
            });
        }
    } catch (e) {
        // Mobile menu non-critical
    }

    try {
        // 2. Sticky Navbar on Scroll
        var navbar = document.querySelector('.navbar');
        if (navbar) {
            window.addEventListener('scroll', function() {
                try {
                    if (window.scrollY > 50) {
                        navbar.classList.add('scrolled');
                    } else {
                        navbar.classList.remove('scrolled');
                    }
                } catch (e) {
                    // Non-critical
                }
            });
        }
    } catch (e) {
        // Navbar non-critical
    }

    try {
        // 3. FAQ Accordion
        var accordionHeaders = document.querySelectorAll('.accordion-header');
        
        accordionHeaders.forEach(function(header) {
            header.addEventListener('click', function() {
                try {
                    var content = header.nextElementSibling;
                    var isActive = header.classList.contains('active');
                    
                    // Close all open accordions
                    accordionHeaders.forEach(function(h) {
                        h.classList.remove('active');
                        if (h.nextElementSibling) {
                            h.nextElementSibling.style.maxHeight = null;
                        }
                    });

                    if (!isActive && content) {
                        header.classList.add('active');
                        content.style.maxHeight = content.scrollHeight + 'px';
                    }
                } catch (e) {
                    // Non-critical
                }
            });
        });
    } catch (e) {
        // Accordion non-critical
    }

    try {
        // 4. Smooth Scrolling for Anchor Links
        document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
            anchor.addEventListener('click', function(e) {
                try {
                    e.preventDefault();
                    var targetId = this.getAttribute('href');
                    if (targetId === '#' || !targetId) return;
                    
                    var targetElement = document.querySelector(targetId);
                    if (targetElement) {
                        // Offset for navbar
                        var offsetTop = targetElement.getBoundingClientRect().top + window.scrollY - 80;
                        window.scrollTo({
                            top: offsetTop,
                            behavior: 'smooth'
                        });
                    }
                } catch (e) {
                    // Non-critical scroll error
                }
            });
        });
    } catch (e) {
        // Anchor links non-critical
    }
});
