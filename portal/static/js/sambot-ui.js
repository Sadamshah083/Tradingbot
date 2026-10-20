/* SamBot UI dialogs: replaces the browser's confirm()/alert() with an accessible modal.
 *   SamDialog.confirm({title, message, detail, confirmText, cancelText, danger}) -> Promise<boolean>
 *   SamDialog.alert({title, message, okText}) -> Promise<void>
 * Any <form> or <a>/<button> with data-confirm="..." is intercepted automatically:
 *   data-confirm-title, data-confirm-detail, data-confirm-ok, data-confirm-cancel, data-confirm-danger
 */
(function () {
  const FOCUSABLE = 'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
  let open = null;

  function el(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; }

  function show(opts) {
    return new Promise(resolve => {
      if (open) open.close(false);
      const prevFocus = document.activeElement;
      const overlay = el('div', 'sd-overlay');
      const dlg = el('div', 'sd-dialog' + (opts.danger ? ' sd-danger' : ''));
      dlg.setAttribute('role', opts.cancel === false ? 'alertdialog' : 'dialog');
      dlg.setAttribute('aria-modal', 'true');
      const id = 'sd-' + Math.random().toString(36).slice(2, 8);
      dlg.setAttribute('aria-labelledby', id + '-t'); dlg.setAttribute('aria-describedby', id + '-d');

      const icon = el('div', 'sd-icon');
      icon.innerHTML = opts.danger
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 4.3 1.8 19a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v5h1"/></svg>';
      const title = el('h2', 'sd-title', opts.title || 'Please confirm'); title.id = id + '-t';
      const body = el('div', 'sd-body'); body.id = id + '-d';
      body.appendChild(el('p', 'sd-msg', opts.message || ''));
      if (opts.detail) body.appendChild(el('p', 'sd-detail', opts.detail));
      const actions = el('div', 'sd-actions');
      const cancel = opts.cancel === false ? null : el('button', 'sd-btn sd-ghost', opts.cancelText || 'Cancel');
      const ok = el('button', 'sd-btn ' + (opts.danger ? 'sd-red' : 'sd-primary'), opts.confirmText || 'OK');
      if (cancel) { cancel.type = 'button'; actions.appendChild(cancel); }
      ok.type = 'button'; actions.appendChild(ok);
      dlg.append(icon, title, body, actions); overlay.appendChild(dlg); document.body.appendChild(overlay);
      document.documentElement.classList.add('sd-lock');
      requestAnimationFrame(() => overlay.classList.add('sd-in'));

      function close(result) {
        if (!open) return; open = null;
        document.removeEventListener('keydown', onKey, true);
        overlay.classList.remove('sd-in'); document.documentElement.classList.remove('sd-lock');
        setTimeout(() => overlay.remove(), 160);
        if (prevFocus && prevFocus.focus) { try { prevFocus.focus(); } catch (e) {} }
        resolve(result);
      }
      function onKey(e) {
        if (e.key === 'Escape') { e.preventDefault(); close(false); return; }
        if (e.key === 'Tab') {   // keep focus inside the dialog
          const f = [...dlg.querySelectorAll(FOCUSABLE)]; if (!f.length) return;
          const first = f[0], last = f[f.length - 1];
          if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
          else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
      }
      document.addEventListener('keydown', onKey, true);
      ok.addEventListener('click', () => close(true));
      if (cancel) cancel.addEventListener('click', () => close(false));
      overlay.addEventListener('mousedown', e => { if (e.target === overlay) close(false); });
      open = {close};
      (opts.danger && cancel ? cancel : ok).focus();   // destructive actions default to the safe choice
    });
  }

  window.SamDialog = {
    confirm: o => show(Object.assign({}, o)),
    alert: o => show(Object.assign({title: 'Notice', confirmText: (o && o.okText) || 'OK', cancel: false}, o)).then(() => undefined),
  };

  function optsFrom(node) {
    const d = node.dataset;
    return {message: d.confirm, title: d.confirmTitle, detail: d.confirmDetail, confirmText: d.confirmOk, cancelText: d.confirmCancel, danger: d.confirmDanger !== undefined};
  }

  document.addEventListener('submit', e => {
    const f = e.target;
    if (!(f instanceof HTMLFormElement) || f.dataset.confirm === undefined || f.dataset.sdOk) return;
    e.preventDefault();
    window.SamDialog.confirm(optsFrom(f)).then(yes => { if (yes) { f.dataset.sdOk = '1'; f.submit(); } });
  }, true);

  document.addEventListener('click', e => {
    const n = e.target.closest('a[data-confirm], button[data-confirm]');
    if (!n || (n.form && n.form.dataset.confirm !== undefined)) return;
    e.preventDefault();
    window.SamDialog.confirm(optsFrom(n)).then(yes => {
      if (!yes) return;
      if (n.tagName === 'A') location.href = n.href;
      else if (n.form) { n.removeAttribute('data-confirm'); n.click(); }
    });
  });
})();
