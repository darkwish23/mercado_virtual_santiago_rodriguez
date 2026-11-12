(() => {
  const form = document.getElementById('producer-form');
  if (!form) return;

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());

    button.disabled = true;
    button.textContent = 'Enviando...';

    try {
      const response = await fetch('/api/solicitud-productor', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'No se pudo enviar la solicitud.');
      form.reset();
      window.Mercado.showToast(result.mensaje);
    } catch (error) {
      window.Mercado.showToast(error.message || 'No se pudo conectar con el servidor.', true);
    } finally {
      button.disabled = false;
      button.innerHTML = 'Enviar solicitud <span>↗</span>';
    }
  });
})();
