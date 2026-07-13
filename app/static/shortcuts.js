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
    if (currentIndex >= cards.length) currentIndex = cards.length - 1;
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

  function setHelp(open) {
    const overlay = document.getElementById('help-overlay');
    if (!overlay) return;
    overlay.classList.toggle('visible', open);
    overlay.setAttribute('aria-hidden', open ? 'false' : 'true');
    if (open) overlay.querySelector('[data-close-help]')?.focus();
  }

  function toggleHelp() {
    const overlay = document.getElementById('help-overlay');
    if (overlay) setHelp(!overlay.classList.contains('visible'));
  }

  function activeQueue() {
    return document.querySelector('.queue-tab.active')?.dataset.queue || null;
  }

  function shouldRemoveFromQueue(queue, action) {
    if (!queue) return false;
    if (queue === 'must_read' || queue === 'maybe_useful') return true;
    if (queue === 'noise') return action !== 'not_relevant';
    if (queue === 'for_content') return ['archive', 'not_relevant'].includes(action);
    return false;
  }

  function decrementActiveQueueCount() {
    const count = document.querySelector('.queue-tab.active span');
    if (!count) return;
    const value = Number.parseInt(count.textContent, 10);
    if (Number.isFinite(value)) count.textContent = String(Math.max(0, value - 1));
  }

  function actionLabel(action) {
    return {
      save: 'Saved to your library.',
      useful: 'Marked useful. Ranking feedback recorded.',
      archive: 'Archived.',
      not_relevant: 'Marked not relevant. Ranking feedback recorded.',
      for_content: 'Added as a content idea.',
      used_for_content: 'Content brief saved.'
    }[action] || 'Article updated.';
  }

  function showToast(message, kind = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.dataset.kind = kind;
    toast.classList.add('visible');
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => toast.classList.remove('visible'), 4000);
  }

  document.addEventListener('keydown', function(e) {
    const activeElement = document.activeElement;
    const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(activeElement.tagName) ||
                    activeElement.isContentEditable;
    const helpOpen = document.getElementById('help-overlay')?.classList.contains('visible');

    if (isInput && e.key !== 'Escape') return;
    if (helpOpen && !['Escape', '?'].includes(e.key)) return;

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
      case 's': handleAction('save'); break;
      case 'a': handleAction('archive'); break;
      case 'u': handleAction('useful'); break;
      case 'n': handleAction('not_relevant'); break;
      case 'o': {
        const link = currentIndex >= 0 ? cards[currentIndex].querySelector('h3 a') : null;
        if (link) window.open(link.href, '_blank');
        break;
      }
      case 'c': {
        const link = currentIndex >= 0 ? cards[currentIndex].querySelector('h3 a') : null;
        if (link) {
          navigator.clipboard.writeText(link.href);
          showToast('Link copied to clipboard.');
        }
        break;
      }
      case 'f': {
        const form = currentIndex >= 0 ? cards[currentIndex].querySelector('.for-content-form') : null;
        const field = form?.querySelector('input, textarea, select');
        if (field) field.focus();
        break;
      }
      case '/': {
        e.preventDefault();
        const searchBox = document.getElementById('search-box');
        if (searchBox) searchBox.focus();
        else window.location.href = '/search';
        break;
      }
      case 'g': {
        const now = Date.now();
        if (now - lastGTime < 500) {
          window.scrollTo({ top: 0, behavior: 'smooth' });
          currentIndex = cards.length ? 0 : -1;
          updateFocus();
          lastGTime = 0;
        } else {
          lastGTime = now;
        }
        break;
      }
      case '?': toggleHelp(); break;
      case 'Escape': setHelp(false); break;
    }
  });

  document.addEventListener('click', function(e) {
    const queueTab = e.target.closest('.queue-tab');
    if (queueTab) {
      document.querySelectorAll('.queue-tab').forEach((tab) => {
        const selected = tab === queueTab;
        tab.classList.toggle('active', selected);
        tab.setAttribute('aria-selected', selected ? 'true' : 'false');
      });
      const url = new URL(window.location.href);
      url.searchParams.set('queue', queueTab.dataset.queue);
      window.history.replaceState({}, '', url);
    }

    if (e.target.closest('[data-open-help]')) setHelp(true);
    if (e.target.closest('[data-close-help]') || e.target.id === 'help-overlay') setHelp(false);
  });

  document.addEventListener('htmx:afterSwap', function(e) {
    refreshCards();

    const path = e.detail.requestConfig?.path || '';
    const match = path.match(/^\/articles\/(\d+)\/(save|archive|useful|not_relevant|for_content|used_for_content)$/);
    if (!match) return;

    const [, articleId, action] = match;
    const queue = activeQueue();
    const card = document.querySelector(`#queue .article-card[data-article-id="${articleId}"]`);
    showToast(actionLabel(action), 'success');

    if (card && shouldRemoveFromQueue(queue, action)) {
      const removedIndex = cards.indexOf(card);
      card.classList.add('is-leaving');
      decrementActiveQueueCount();
      window.setTimeout(() => {
        card.remove();
        refreshCards();
        if (cards.length) {
          currentIndex = Math.min(Math.max(removedIndex, 0), cards.length - 1);
          updateFocus(false);
        }
      }, 220);
    }
  });

  document.addEventListener('htmx:responseError', function(e) {
    const status = e.detail.xhr ? e.detail.xhr.status : 'unknown';
    showToast(`Request failed (${status}). Your previous state was kept.`, 'error');
  });

  document.addEventListener('htmx:sendError', function() {
    showToast('Could not reach INTEL. Check that the dashboard is running.', 'error');
  });

  window.addEventListener('DOMContentLoaded', refreshCards);
})();
