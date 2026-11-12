(() => {
  const input = document.getElementById('profile-photo-input');
  const form = document.getElementById('profile-photo-form');
  const trigger = document.getElementById('profile-avatar-trigger');
  const modal = document.getElementById('profile-photo-modal');
  const close = document.getElementById('profile-photo-close');
  const area = document.getElementById('profile-photo-drag-area');
  const preview = document.getElementById('profile-photo-live');
  const zoom = document.getElementById('profile-photo-zoom');
  const save = document.getElementById('profile-photo-save');
  const hint = document.getElementById('profile-photo-hint');
  const cropX = document.getElementById('profile-photo-crop-x');
  const cropY = document.getElementById('profile-photo-crop-y');
  const cropSize = document.getElementById('profile-photo-crop-size');
  if (!input || !form || !trigger || !modal || !area || !preview || !zoom || !save) return;

  let selected = null, objectUrl = null, isGif = false;
  let imageWidth = 0, imageHeight = 0, baseScale = 1, scale = 1;
  let offsetX = 0, offsetY = 0, drag = null;
  const areaSize = () => area.clientWidth;
  const clampOffsets = () => {
    const size = areaSize(), renderedW = imageWidth * baseScale * scale;
    const renderedH = imageHeight * baseScale * scale;
    const minX = size - renderedW, minY = size - renderedH;
    offsetX = Math.min(0, Math.max(minX, offsetX));
    offsetY = Math.min(0, Math.max(minY, offsetY));
  };
  const paint = () => {
    const size = areaSize(), renderedW = imageWidth * baseScale * scale;
    const renderedH = imageHeight * baseScale * scale;
    preview.style.width = `${renderedW}px`;
    preview.style.height = `${renderedH}px`;
    preview.style.left = `${(size - renderedW) / 2 + offsetX}px`;
    preview.style.top = `${(size - renderedH) / 2 + offsetY}px`;
    const sourceSide = size / (baseScale * scale);
    const sx = (imageWidth - sourceSide) / 2 - offsetX / (baseScale * scale);
    const sy = (imageHeight - sourceSide) / 2 - offsetY / (baseScale * scale);
    cropX.value = String(Math.max(0, Math.min(1, sx / imageWidth)));
    cropY.value = String(Math.max(0, Math.min(1, sy / imageHeight)));
    cropSize.value = String(Math.max(0, Math.min(1, sourceSide / Math.min(imageWidth, imageHeight))));
  };
  const open = () => { modal.hidden = false; document.body.classList.add('profile-photo-modal-open'); };
  const shut = () => { modal.hidden = true; document.body.classList.remove('profile-photo-modal-open'); };
  trigger.addEventListener('click', () => input.click());
  close?.addEventListener('click', shut);
  modal.addEventListener('click', e => { if (e.target === modal) shut(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !modal.hidden) shut(); });

  zoom.addEventListener('input', () => {
    const oldScale = scale; scale = Number(zoom.value);
    const factor = scale / oldScale;
    offsetX *= factor; offsetY *= factor;
    clampOffsets(); paint();
  });
  area.addEventListener('pointerdown', e => {
    drag = {x:e.clientX, y:e.clientY, ox:offsetX, oy:offsetY};
    area.setPointerCapture(e.pointerId);
  });
  area.addEventListener('pointermove', e => {
    if (!drag) return;
    offsetX = drag.ox + e.clientX - drag.x;
    offsetY = drag.oy + e.clientY - drag.y;
    clampOffsets(); paint();
  });
  ['pointerup','pointercancel','lostpointercapture'].forEach(type => area.addEventListener(type, () => drag = null));

  input.addEventListener('change', () => {
    selected = input.files?.[0] || null;
    if (!selected) return;
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(selected);
    isGif = selected.type === 'image/gif' || /\.gif$/i.test(selected.name);
    preview.onload = () => {
      imageWidth = preview.naturalWidth; imageHeight = preview.naturalHeight;
      baseScale = areaSize() / Math.min(imageWidth, imageHeight);
      scale = 1; offsetX = 0; offsetY = 0; zoom.value = '1';
      paint(); save.disabled = false;
    };
    preview.src = objectUrl;
    hint.textContent = isGif
      ? 'GIF animado: arrastra para elegir el encuadre y usa el zoom. Se conservará la animación.'
      : 'Arrastra la imagen para elegir el encuadre dentro del círculo y usa el zoom.';
    save.disabled = true; save.textContent = 'Guardar cambios'; open();
  });

  form.addEventListener('submit', async e => {
    if (!selected || isGif || !selected.type.startsWith('image/')) return;
    e.preventDefault(); save.disabled = true; save.textContent = 'Preparando imagen…';
    try {
      const bitmap = await createImageBitmap(selected);
      const side = Number(cropSize.value) * Math.min(bitmap.width, bitmap.height);
      const sx = Number(cropX.value) * bitmap.width;
      const sy = Number(cropY.value) * bitmap.height;
      const canvas = document.createElement('canvas'); canvas.width = 640; canvas.height = 640;
      canvas.getContext('2d').drawImage(bitmap, sx, sy, side, side, 0, 0, 640, 640);
      bitmap.close?.();
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/webp', .92));
      if (!blob) throw new Error('No se pudo procesar');
      const cropped = new File([blob], selected.name.replace(/\.[^.]+$/, '') + '-perfil.webp', {type:'image/webp'});
      const transfer = new DataTransfer(); transfer.items.add(cropped); input.files = transfer.files;
      form.submit();
    } catch (_) {
      hint.textContent = 'No fue posible ajustar la imagen. Intenta con otro archivo.';
      save.disabled = false; save.textContent = 'Guardar cambios';
    }
  });
})();
