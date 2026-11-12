(() => {
  const mercado = window.Mercado;
  const cart = mercado.getCart();
  const cards = [...document.querySelectorAll('.product-card')];
  const search = document.getElementById('search');
  const category = document.getElementById('category');
  const sortSelect = document.getElementById('sort');
  const productGrid = document.getElementById('products');
  const emptyState = document.getElementById('empty-state');
  const countLabel = document.getElementById('catalog-count');
  const cartSummary = document.getElementById('cart-summary');
  const cartTotal = document.getElementById('cart-total');
  const cartItemsList = document.getElementById('cart-items-list');
  const reserveButton = document.getElementById('reserve-btn');
  const dialog = document.getElementById('reserve-dialog');
  const reservationForm = document.getElementById('reservation-form');
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

  const originalOrder = new Map(cards.map((card, index) => [card.dataset.productId, index]));

  const catalog = Object.fromEntries(cards.map(card => [card.dataset.productId, {
    name: card.querySelector('h3').textContent.trim(),
    price: Number(card.querySelector('.price b').textContent.replace(/[^0-9]/g, '')),
    unit: card.querySelector('.price small').textContent.trim().replace(/^\/\s*/, '')
  }]));

  function normalizeText(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLocaleLowerCase('es');
  }

  function applyFilters() {
    const query = normalizeText(search.value.trim());
    const selectedCategory = category.value;
    let visible = 0;

    cards.forEach(card => {
      const searchableText = normalizeText(card.dataset.search || card.dataset.name);
      const matchesText = searchableText.includes(query);
      const matchesCategory = selectedCategory === 'all' || card.dataset.category === selectedCategory;
      const show = matchesText && matchesCategory;
      card.hidden = !show;
      if (show) visible++;
    });

    countLabel.textContent = `${visible} ${visible === 1 ? 'producto encontrado' : 'productos encontrados'}`;
    emptyState.hidden = visible !== 0;
  }

  function applySorting() {
    const mode = sortSelect?.value || 'featured';
    const sortedCards = [...cards].sort((a, b) => {
      const idA = a.dataset.productId;
      const idB = b.dataset.productId;
      const productA = catalog[idA];
      const productB = catalog[idB];

      if (mode === 'name-asc') {
        return productA.name.localeCompare(productB.name, 'es');
      }
      if (mode === 'price-asc') return productA.price - productB.price;
      if (mode === 'price-desc') return productB.price - productA.price;
      return originalOrder.get(idA) - originalOrder.get(idB);
    });

    sortedCards.forEach(card => productGrid.appendChild(card));
  }

  function renderCart() {
    const entries = Object.entries(cart).filter(([id, quantity]) => catalog[id] && Number(quantity) > 0);
    const quantityTotal = entries.reduce((sum, [, quantity]) => sum + Number(quantity), 0);
    const priceTotal = entries.reduce((sum, [id, quantity]) => sum + catalog[id].price * Number(quantity), 0);

    cartSummary.textContent = quantityTotal
      ? `${quantityTotal} ${quantityTotal === 1 ? 'unidad seleccionada' : 'unidades seleccionadas'}`
      : 'Aún no has agregado productos.';
    cartTotal.textContent = mercado.formatMoney(priceTotal);
    reserveButton.disabled = quantityTotal === 0;
    mercado.saveCart(cart);

    cartItemsList.replaceChildren();

    entries.forEach(([id, quantity]) => {
      const product = catalog[id];
      const row = document.createElement('div');
      row.className = 'cart-item-row';

      const info = document.createElement('div');
      info.className = 'cart-item-info';

      const name = document.createElement('b');
      name.className = 'cart-item-name';
      name.textContent = product.name;

      const quantityText = document.createElement('small');
      quantityText.textContent = `${quantity} × ${product.unit}`;
      info.append(name, quantityText);

      const actions = document.createElement('div');
      actions.className = 'cart-item-actions';

      const subtotal = document.createElement('strong');
      subtotal.textContent = mercado.formatMoney(product.price * Number(quantity));

      const removeButton = document.createElement('button');
      removeButton.type = 'button';
      removeButton.className = 'cart-remove-btn';
      removeButton.dataset.removeProduct = id;
      removeButton.setAttribute('aria-label', `Eliminar ${product.name}`);
      removeButton.title = 'Eliminar producto';
      removeButton.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="m19 6-1 14H6L5 6"/><path d="M10 11v5"/><path d="M14 11v5"/>
        </svg>`;

      actions.append(subtotal, removeButton);
      row.append(info, actions);
      cartItemsList.appendChild(row);
    });

    document.querySelectorAll('[data-add-product]').forEach(button => {
      const selected = Number(cart[button.dataset.addProduct] || 0);
      button.classList.toggle('is-added', selected > 0);
      button.textContent = selected > 0 ? `✓ ${selected}` : '+';
    });
  }

  cartItemsList.addEventListener('click', event => {
    const button = event.target.closest('[data-remove-product]');
    if (!button) return;
    const id = button.dataset.removeProduct;
    if (!catalog[id]) return;

    const productName = catalog[id].name;
    delete cart[id];
    renderCart();
    mercado.showToast(`${productName} se eliminó del carrito.`);
  });

  // Espera un instante al escribir para no recalcular el catálogo por cada tecla.
  let searchTimer;
  search.addEventListener('input', () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(applyFilters, 100);
  });
  category.addEventListener('change', applyFilters);
  sortSelect?.addEventListener('change', () => {
    applySorting();
    applyFilters();
  });

  function resetFilters() {
    search.value = '';
    category.value = 'all';
    if (sortSelect) sortSelect.value = 'featured';
    applySorting();
    applyFilters();
    search.focus();
  }

  document.getElementById('clear-filters')?.addEventListener('click', resetFilters);
  document.getElementById('empty-clear-filters')?.addEventListener('click', resetFilters);

  // Si una fotografía no existe o no se puede cargar, muestra el emoji de respaldo.
  document.querySelectorAll('.product-photo').forEach(image => {
    image.addEventListener('error', () => {
      image.hidden = true;
      const fallback = image.nextElementSibling;
      if (fallback?.classList.contains('product-image-fallback')) {
        fallback.hidden = false;
      }
    }, { once: true });
  });

  document.querySelectorAll('[data-add-product]').forEach(button => {
    button.addEventListener('click', () => {
      const id = button.dataset.addProduct;
      cart[id] = Math.min(99, Number(cart[id] || 0) + 1);
      renderCart();
      mercado.showToast(`${catalog[id].name} se agregó a tu selección.`);
    });
  });

  function renderDialogItems() {
    const entries = Object.entries(cart).filter(([id, quantity]) => catalog[id] && Number(quantity) > 0);
    const container = document.getElementById('dialog-items');
    container.replaceChildren();

    entries.forEach(([id, quantity]) => {
      const row = document.createElement('div');
      row.className = 'dialog-item';
      const details = document.createElement('div');
      const name = document.createElement('b');
      name.textContent = catalog[id].name;
      const unit = document.createElement('small');
      unit.textContent = `${quantity} × ${catalog[id].unit}`;
      details.append(name, unit);
      const price = document.createElement('strong');
      price.textContent = mercado.formatMoney(catalog[id].price * Number(quantity));
      row.append(details, price);
      container.appendChild(row);
    });

    const total = entries.reduce((sum, [id, quantity]) => sum + catalog[id].price * Number(quantity), 0);
    const totalRow = document.createElement('div');
    totalRow.className = 'dialog-total';
    const totalLabel = document.createElement('span');
    totalLabel.textContent = 'Total estimado';
    const totalValue = document.createElement('b');
    totalValue.textContent = mercado.formatMoney(total);
    totalRow.append(totalLabel, totalValue);
    container.appendChild(totalRow);
  }

  reserveButton.addEventListener('click', () => {
    renderDialogItems();
    dialog.showModal();
  });

  document.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  });

  reservationForm.addEventListener('submit', async event => {
    event.preventDefault();
    const submit = document.getElementById('submit-reservation');
    const formData = new FormData(reservationForm);
    const payload = {
      name: formData.get('name'),
      phone: formData.get('phone'),
      notes: formData.get('notes'),
      items: { ...cart }
    };

    submit.disabled = true;
    submit.textContent = 'Enviando...';

    try {
      const response = await fetch('/api/reservas', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'No se pudo registrar la reserva.');

      Object.keys(cart).forEach(key => delete cart[key]);
      mercado.saveCart(cart);
      renderCart();
      reservationForm.reset();
      dialog.close();
      mercado.showToast(`¡Reserva registrada! Tu código es ${result.codigo}.`);
    } catch (error) {
      mercado.showToast(error.message || 'No se pudo conectar con el servidor.', true);
    } finally {
      submit.disabled = false;
      submit.innerHTML = 'Confirmar reserva <span>↗</span>';
    }
  });

  applySorting();
  renderCart();
  applyFilters();
})();
