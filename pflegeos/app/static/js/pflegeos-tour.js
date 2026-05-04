/**
 * PflegeOS Guided Tour Engine
 * Легковесный онбординг без зависимостей (только Bootstrap CSS)
 *
 * Использование:
 *   const tour = new PflegeOSTour(steps, { storageKey: 'my_tour_v1' });
 *   tour.start();           // запустить (пропустит если уже завершён)
 *   tour.start(true);       // принудительно, даже если завершён
 */

class PflegeOSTour {
  constructor(steps, options = {}) {
    this.steps = steps;
    this.currentIndex = 0;
    this.storageKey = options.storageKey || 'pflegeos_tour_default';
    this.onFinish = options.onFinish || null;
    this.tooltipEl = null;
    this.overlayEl = null;
    this.prevHighlighted = null;
    this.active = false;
  }

  // ── Публичные методы ────────────────────────────────────────

  start(force = false) {
    if (!force && localStorage.getItem(this.storageKey)) return;
    this.currentIndex = 0;
    this.active = true;
    this._showStep(0);
  }

  next() {
    this._clearHighlight();
    if (this.currentIndex < this.steps.length - 1) {
      this.currentIndex++;
      this._showStep(this.currentIndex);
    } else {
      this.finish();
    }
  }

  prev() {
    if (this.currentIndex > 0) {
      this._clearHighlight();
      this.currentIndex--;
      this._showStep(this.currentIndex);
    }
  }

  skip() {
    this.finish();
  }

  finish() {
    this._clearHighlight();
    this._removeTooltip();
    this._removeOverlay();
    localStorage.setItem(this.storageKey, '1');
    this.active = false;
    if (this.onFinish) this.onFinish();
  }

  reset() {
    localStorage.removeItem(this.storageKey);
  }

  // ── Внутренние методы ───────────────────────────────────────

  _showStep(index) {
    this._clearHighlight();
    this._removeTooltip();

    const step = this.steps[index];
    if (!step) { this.finish(); return; }

    // Центральный шаг (без target)
    if (!step.element || step.position === 'center') {
      this._showCenterStep(step);
      return;
    }

    const el = document.querySelector(step.element);
    if (!el) {
      // Элемент не найден — пропустить шаг
      console.warn(`[PflegeOSTour] Element not found: ${step.element}`);
      this.next();
      return;
    }

    // Скролл к элементу
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });

    setTimeout(() => {
      this._highlightElement(el);
      this._renderTooltip(step, el);
    }, 300);
  }

  _showCenterStep(step) {
    // Полноэкранный оверлей с карточкой по центру
    this._removeOverlay();

    const overlay = document.createElement('div');
    overlay.className = 'tour-center-overlay';
    overlay.id = 'tourCenterOverlay';

    const total = this.steps.length;
    const current = this.currentIndex + 1;
    const progress = Math.round((current / total) * 100);

    overlay.innerHTML = `
      <div class="tour-center-card">
        ${step.icon ? `<div class="tour-center-icon">${step.icon}</div>` : ''}
        <div class="tour-center-title">${step.title}</div>
        <div class="tour-center-text">${step.content}</div>

        <div class="tour-progress mb-3">
          <div class="tour-progress-bar" style="width:${progress}%"></div>
        </div>

        <div class="tour-buttons justify-content-center">
          ${this.currentIndex > 0
            ? `<button class="tour-btn-prev" onclick="window.__activeTour.prev()">← Zurück</button>`
            : ''}
          <button class="tour-btn-next" onclick="window.__activeTour.next()">
            ${current === total ? 'Fertig ✓' : 'Weiter →'}
          </button>
          ${current < total
            ? `<button class="tour-btn-skip" onclick="window.__activeTour.skip()">Tour überspringen</button>`
            : ''}
        </div>
      </div>`;

    document.body.appendChild(overlay);
    this.overlayEl = overlay;
    window.__activeTour = this;
  }

  _highlightElement(el) {
    el.classList.add('tour-spotlight');
    this.prevHighlighted = el;
  }

  _clearHighlight() {
    if (this.prevHighlighted) {
      this.prevHighlighted.classList.remove('tour-spotlight');
      this.prevHighlighted = null;
    }
    this._removeOverlay();
  }

  _removeOverlay() {
    const el = document.getElementById('tourCenterOverlay');
    if (el) el.remove();
    this.overlayEl = null;
  }

  _removeTooltip() {
    if (this.tooltipEl) {
      this.tooltipEl.remove();
      this.tooltipEl = null;
    }
  }

  _renderTooltip(step, targetEl) {
    const rect = targetEl.getBoundingClientRect();
    const total = this.steps.length;
    const current = this.currentIndex + 1;
    const progress = Math.round((current / total) * 100);

    const tooltip = document.createElement('div');
    tooltip.className = 'tour-tooltip';
    tooltip.id = 'tourTooltip';

    tooltip.innerHTML = `
      <div class="tour-tooltip-header">
        <span class="tour-step-badge">${current} / ${total}</span>
        <span class="tour-tooltip-title">${step.title}</span>
      </div>

      <div class="tour-progress">
        <div class="tour-progress-bar" style="width:${progress}%"></div>
      </div>

      <div class="tour-tooltip-content">${step.content}</div>

      <div class="tour-buttons">
        ${current > 1
          ? `<button class="tour-btn-prev" onclick="window.__activeTour.prev()">←</button>`
          : ''}
        <button class="tour-btn-next" onclick="window.__activeTour.next()">
          ${current === total ? '✓ Fertig' : 'Weiter →'}
        </button>
        ${current < total
          ? `<button class="tour-btn-skip" onclick="window.__activeTour.skip()">Überspringen</button>`
          : ''}
      </div>`;

    document.body.appendChild(tooltip);
    this.tooltipEl = tooltip;
    window.__activeTour = this;

    this._positionTooltip(tooltip, rect, step.position || 'auto');
  }

  _positionTooltip(tooltip, rect, position) {
    const tw = tooltip.offsetWidth || 320;
    const th = tooltip.offsetHeight || 160;
    const gap = 16;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let top, left, arrowClass = 'arrow-none';

    // Auto: выбрать лучшую позицию
    if (position === 'auto') {
      const spaceBelow = vh - rect.bottom;
      const spaceAbove = rect.top;
      const spaceRight = vw - rect.right;
      position = spaceBelow >= th + gap ? 'bottom'
               : spaceAbove >= th + gap ? 'top'
               : spaceRight >= tw + gap ? 'right'
               : 'left';
    }

    switch (position) {
      case 'bottom':
        top = rect.bottom + gap;
        left = Math.max(8, Math.min(rect.left, vw - tw - 8));
        arrowClass = 'arrow-bottom';
        break;
      case 'top':
        top = rect.top - th - gap;
        left = Math.max(8, Math.min(rect.left, vw - tw - 8));
        arrowClass = 'arrow-top';
        break;
      case 'right':
        top = rect.top + (rect.height - th) / 2;
        left = rect.right + gap;
        arrowClass = 'arrow-right';
        break;
      case 'left':
        top = rect.top + (rect.height - th) / 2;
        left = rect.left - tw - gap;
        arrowClass = 'arrow-left';
        break;
      default:
        top = rect.bottom + gap;
        left = Math.max(8, Math.min(rect.left, vw - tw - 8));
        arrowClass = 'arrow-bottom';
    }

    // Не выходить за края экрана
    top = Math.max(8, Math.min(top, vh - th - 8));
    left = Math.max(8, Math.min(left, vw - tw - 8));

    tooltip.style.top  = `${top}px`;
    tooltip.style.left = `${left}px`;
    tooltip.classList.add(arrowClass);
  }
}


// ── Floating Help Button ────────────────────────────────────────

function initTourHelpButton(tourFactory) {
  // Создаёт кнопку "?" внизу справа для перезапуска тура
  const btn = document.createElement('button');
  btn.id = 'tourHelpBtn';
  btn.title = 'Hilfe & Tour';
  btn.innerHTML = `<div class="tour-pulse"></div><span style="position:relative;z-index:1">?</span>`;
  btn.addEventListener('click', () => {
    const tour = tourFactory();
    tour.start(true); // force restart
  });
  document.body.appendChild(btn);
}


// ── Глобальный хелпер для страниц ──────────────────────────────

window.PflegeOSTour = PflegeOSTour;
window.initTourHelpButton = initTourHelpButton;
