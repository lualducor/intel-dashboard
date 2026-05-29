(function() {
  let cards = [];
  let currentIndex = -1;
  let lastGTime = 0;

  function refreshCards() {
    const queue = document.getElementById('queue');
    if (!queue) {
      cards = [];
      currentIndex = -1;
      return;
    }
    cards = Array.from(queue.querySelectorAll('.article-card'));
    
    // Ensure currentIndex is still valid after refresh
    if (currentIndex >= cards.length) {
      currentIndex = cards.length - 1;
    }
    
    // If we have cards but none is focused, we don't force focus here 
    // to avoid jumping on every HTMX swap unless the user was already navigating.
    updateFocus(false); 
  }

  function updateFocus(scroll = true) {
    cards.forEach((card, index) => {
      if (index === currentIndex) {
        card.setAttribute('data-focused', 'true');
        if (scroll) {
          card.focus();
          card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      } else {
        card.removeAttribute('data-focused');
      }
    });
  }

  function handleAction(actionPath) {
    if (currentIndex < 0 || currentIndex >= cards.length) return;
    const card = cards[currentIndex];
    const id = card.getAttribute('data-article-id');
    if (!id) return;

    htmx.ajax('POST', `/articles/${id}/${actionPath}`, {
      target: card,
      swap: 'outerHTML'
    });
  }

  function toggleHelp() {
    const overlay = document.getElementById('help-overlay');
    if (overlay) {
      overlay.classList.toggle('visible');
    }
  }

  document.addEventListener('keydown', function(e) {
    const isInput = ['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName) || 
                    document.activeElement.isContentEditable;

    if (isInput && e.key !== 'Escape') return;

    switch (e.key) {
      case 'j':
        if (currentIndex < cards.length - 1) {
          currentIndex++;
          updateFocus();
        }
        break;
      case 'k':
        if (currentIndex > 0) {
          currentIndex--;
          updateFocus();
        }
        break;
      case 's':
        handleAction('save');
        break;
      case 'a':
        handleAction('archive');
        break;
      case 'u':
        handleAction('useful');
        break;
      case 'n':
        handleAction('not_relevant');
        break;
      case 'o':
        if (currentIndex >= 0) {
          const link = cards[currentIndex].querySelector('h3 a');
          if (link) window.open(link.href, '_blank');
        }
        break;
      case 'c':
        if (currentIndex >= 0) {
          const link = cards[currentIndex].querySelector('h3 a');
          if (link) navigator.clipboard.writeText(link.href);
        }
        break;
      case 'f':
        if (currentIndex >= 0) {
          const form = cards[currentIndex].querySelector('.for-content-form');
          if (form) {
             const textarea = form.querySelector('textarea');
             if (textarea) textarea.focus();
          }
        }
        break;
      case '/':
        e.preventDefault();
        const searchBox = document.getElementById('search-box');
        if (searchBox) {
          searchBox.focus();
        } else {
          window.location.href = '/search';
        }
        break;
      case 'g':
        const now = Date.now();
        if (now - lastGTime < 500) {
          window.scrollTo({ top: 0, behavior: 'smooth' });
          currentIndex = 0;
          updateFocus();
          lastGTime = 0;
        } else {
          lastGTime = now;
        }
        break;
      case '?':
        toggleHelp();
        break;
      case 'Escape':
        const overlay = document.getElementById('help-overlay');
        if (overlay && overlay.classList.contains('visible')) {
          overlay.classList.remove('visible');
        }
        break;
    }
  });

  document.addEventListener('htmx:afterSwap', function(e) {
    refreshCards();
  });

  window.addEventListener('DOMContentLoaded', refreshCards);
})();
