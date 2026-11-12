(() => {
  const menuButton = document.getElementById('menu-toggle');
  const nav = document.getElementById('main-nav');
  if (menuButton && nav) {
    menuButton.addEventListener('click', () => {
      const isOpen = nav.classList.toggle('is-open');
      menuButton.setAttribute('aria-expanded', String(isOpen));
      menuButton.setAttribute('aria-label', isOpen ? 'Cerrar menú' : 'Abrir menú');
    });
    nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
      nav.classList.remove('is-open');
      menuButton.setAttribute('aria-expanded', 'false');
    }));
  }

  window.Mercado = {
    getCart() {
      try { return JSON.parse(localStorage.getItem('mercadoCart') || '{}'); }
      catch { return {}; }
    },
    saveCart(cart) {
      localStorage.setItem('mercadoCart', JSON.stringify(cart));
      this.updateCartBadge(cart);
    },
    updateCartBadge(cart = this.getCart()) {
      const total = Object.values(cart).reduce((sum, value) => sum + Number(value || 0), 0);
      document.querySelectorAll('[data-cart-count]').forEach(el => {
        el.textContent = String(total);
        el.classList.toggle('is-empty', total === 0);
      });
    },
    showToast(message, isError = false) {
      const toast = document.getElementById('toast');
      if (!toast) return;
      toast.textContent = message;
      toast.classList.toggle('toast-error', isError);
      toast.classList.add('show');
      window.clearTimeout(this.toastTimer);
      this.toastTimer = window.setTimeout(() => toast.classList.remove('show'), 4200);
    },
    formatMoney(value) {
      return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(value);
    }
  };
  window.Mercado.updateCartBadge();
})();
