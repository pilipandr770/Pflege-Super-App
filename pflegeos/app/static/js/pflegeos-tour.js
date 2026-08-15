/* ── PflegeOS Onboarding Tour ─────────────────────────────── */
/* Vanilla JS, no dependencies. Auto-starts once per user.    */

(function () {
  'use strict';

  /* ── Tour-Schritte ───────────────────────────────────────── */
  var STEPS = [
    {
      selector: null,   // null = zentrierte Karte ohne Highlight
      icon: '🏥',
      title: 'Willkommen in PflegeOS!',
      body: 'Diese kurze Tour zeigt Ihnen alle wichtigen Funktionen. Sie dauert ca. 2 Minuten und kann jederzeit übersprungen werden.',
    },
    {
      selector: 'a[href="/dashboard"]',
      icon: '📊',
      title: 'Dashboard',
      body: '<strong>Ihre Schaltzentrale.</strong> Tagesübersicht: offene Leistungen, Schicht­belegung, ablaufende Verträge und HKP-Verordnungen auf einen Blick.',
    },
    {
      selector: 'a[href*="/patients"]',
      icon: '👥',
      title: 'Patienten',
      body: '<strong>Zentrale Patientenverwaltung.</strong> Stammdaten, Pflegegrad, Krankenkasse, Hausarzt. Von hier aus gelangen Sie zu SIS, Medikamenten, Wunden und allen Dokumenten.',
    },
    {
      selector: 'a[href*="/sis"]',
      icon: '📋',
      title: 'SIS – Strukturierte Informationssammlung',
      body: '<strong>MDK-konforme Pflegeplanung.</strong> Alle 6 SIS-Themenfelder digital erfassen, Risiken bewerten und als PDF exportieren — bereit für die MDK-Prüfung.',
    },
    {
      selector: 'a[href*="/medications"]',
      icon: '💊',
      title: 'Medikamente & BtM-Buch',
      body: '<strong>Medikationspläne & Betäubungsmittel.</strong> Aktuelle Pläne mit Mo/Mi/Ab/Nacht-Spalten, BtM-Buch mit gesetzlicher Dokumentation und automatischer Bestandsführung.',
    },
    {
      selector: 'a[href*="/hkp"]',
      icon: '📄',
      title: 'HKP-Verordnungen (Muster 12)',
      body: '<strong>§37 SGB V digitalisiert.</strong> Häusliche Krankenpflege-Verordnungen erfassen, Gültigkeitszeitraum verwalten, Statusverfolgung und PDF-Druck.',
    },
    {
      selector: 'a[href*="/wounds"]',
      icon: '🩹',
      title: 'Wundmanagement',
      body: '<strong>KI-gestützte Wundanalyse.</strong> Fotos hochladen, Claude Vision analysiert automatisch Wundgröße und -tiefe. Verlaufsdokumentation für MDK-Prüfungen.',
    },
    {
      selector: 'a[href*="/touren"]',
      icon: '🗺️',
      title: 'Tourenplanung',
      body: '<strong>Ambulante Touren managen.</strong> Wochenkalender, Drag-&-Drop-Reihenfolge, Google Maps-Links und Tourzettel als PDF — optimiert für den Pflegealltag.',
    },
    {
      selector: 'a[href*="/schichtplan"]',
      icon: '📅',
      title: 'Schichtplan',
      body: '<strong>Digitale Dienstplanung.</strong> Monatlicher Dienstplan, Schichtvorlagen, Abwesenheiten und Überstunden — für alle Mitarbeiter auf einem Blick.',
    },
    {
      selector: 'a[href*="/ki-dienstplan"]',
      icon: '🤖',
      title: 'KI-Dienstplan',
      body: '<strong>Claude AI plant Ihren Dienst.</strong> Einfach Anforderungen eingeben und der KI-Dienstplan-Generator erstellt automatisch einen optimierten Monatsplan.',
    },
    {
      selector: 'a[href*="/leistungen"]',
      icon: '✅',
      title: 'Leistungskatalog & Nachweis',
      body: '<strong>SGB XI-Leistungen dokumentieren.</strong> Erbrachte Pflegeleistungen erfassen, monatliche Leistungsnachweise für Krankenkassen als PDF exportieren.',
    },
    {
      selector: 'a[href*="/vertraege"]',
      icon: '📝',
      title: 'Pflegeverträge',
      body: '<strong>Vertragsverwaltung digital.</strong> Pflegeverträge anlegen, Laufzeiten überwachen, automatische Benachrichtigung bei ablaufenden Verträgen.',
    },
    {
      selector: 'a[href*="/rechnungen"]',
      icon: '💶',
      title: 'Privatrechnungen',
      body: '<strong>Selbstzahler-Abrechnung.</strong> Individuelle Rechnungen für Privatpatienten erstellen, PDF-Export mit Firmenlogo und gesetzlichen Pflichtangaben.',
    },
    {
      selector: 'a[href*="/fortbildungen"]',
      icon: '🎓',
      title: 'Fortbildungsnachweis',
      body: '<strong>MDK-konforme Weiterbildung.</strong> Pflichtfortbildungen, Zertifikate hochladen, Jahresübersicht je Mitarbeiter und Nachweis-PDF für den MDK.',
    },
    {
      selector: 'a[href*="/gkv"]',
      icon: '🏦',
      title: 'GKV-Abrechnung (SGB XI)',
      body: '<strong>Kassenabrechnung einfach gemacht.</strong> Leistungen für alle Pflegegrade abrufen, Abrechnungsdateien im EDIFACT-Format für Krankenkassen erstellen.',
    },
    {
      selector: 'a[href*="/lohn"]',
      icon: '💼',
      title: 'Lohnabrechnung (DATEV)',
      body: '<strong>DATEV-Export für den Steuerberater.</strong> Monatliche Gehaltsabrechnungen aufbereiten und als DATEV-Datei exportieren — direkt an den Lohnbuchhalter.',
    },
    {
      selector: 'a[href*="/qm"]',
      icon: '🏆',
      title: 'QM-Modul',
      body: '<strong>Qualitätsmanagement & Prüfungen.</strong> Interne QM-Prüfungen planen, durchführen, Mängel dokumentieren und Maßnahmen verfolgen.',
    },
    {
      selector: 'a[href*="/employees"]',
      icon: '👤',
      title: 'Mitarbeiterverwaltung',
      body: '<strong>Ihr Team im Blick.</strong> Mitarbeiterstammdaten, Qualifikationen, Führerschein und Fahrzeugzuordnung — alle Personalinformationen an einem Ort.',
    },
    {
      selector: 'a[href*="/fuhrpark"]',
      icon: '🚗',
      title: 'Fuhrpark',
      body: '<strong>Fahrzeugverwaltung.</strong> KFZ-Register, Hauptuntersuchungen, Versicherungen und Fahrzeugzuordnung zu Mitarbeitern — nichts mehr vergessen.',
    },
    {
      selector: 'a[href*="/standorte"]',
      icon: '📍',
      title: 'Standorte & Geräte',
      body: '<strong>Multi-Standort-Verwaltung.</strong> Mehrere Pflegebereiche oder Standorte anlegen und Geräte registrieren — für wachsende Pflegeorganisationen.',
    },
    {
      selector: 'a[href*="/audit"]',
      icon: '🔍',
      title: 'Audit-Log',
      body: '<strong>Lückenlose Nachvollziehbarkeit.</strong> Alle Änderungen im System werden protokolliert — Wer hat wann was geändert? Für MDK und interne Kontrolle.',
    },
    {
      selector: 'a[href*="/settings"]',
      icon: '⚙️',
      title: 'Einstellungen',
      body: '<strong>PflegeOS konfigurieren.</strong> Firmendaten, Logo, Rechnungsvorlage, Benutzerverwaltung und Schnittstelleneinstellungen.',
    },
    {
      selector: null,
      icon: '🎉',
      title: 'Tour abgeschlossen!',
      body: 'Sie kennen jetzt alle Funktionen von PflegeOS. Bei Fragen steht Ihnen unser Support jederzeit zur Verfügung. Viel Erfolg!',
      finish: true,
    },
  ];

  /* ── Zustand ─────────────────────────────────────────────── */
  var currentStep = 0;
  var card = null;
  var highlight = null;
  var masks = [];
  var welcomeModal = null;
  var active = false;

  /* ── Hilfsfunktionen ─────────────────────────────────────── */
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  function getTarget(step) {
    if (!step.selector) return null;
    var t = document.querySelector(step.selector);
    if (!t) {
      // Fallback: partial href match
      var parts = step.selector.match(/href\*="([^"]+)"/);
      if (parts) {
        t = document.querySelector('a[href*="' + parts[1] + '"]');
      }
    }
    return t;
  }

  /* ── Konfetti ────────────────────────────────────────────── */
  function spawnConfetti() {
    var colors = ['#1a5f7a', '#57d9f0', '#16a34a', '#f59e0b', '#ef4444', '#8b5cf6'];
    for (var i = 0; i < 60; i++) {
      (function (i) {
        setTimeout(function () {
          var p = el('div', 'confetti-piece');
          p.style.left = Math.random() * 100 + 'vw';
          p.style.top = '-20px';
          p.style.background = colors[Math.floor(Math.random() * colors.length)];
          p.style.animationDelay = Math.random() * 0.5 + 's';
          p.style.width = (8 + Math.random() * 8) + 'px';
          p.style.height = (8 + Math.random() * 8) + 'px';
          document.body.appendChild(p);
          setTimeout(function () { p.remove(); }, 3000);
        }, i * 25);
      })(i);
    }
  }

  /* ── Overlay / Highlight ──────────────────────────────────── */
  function createMasks() {
    masks.forEach(function (m) { m.remove(); });
    masks = [];
    for (var i = 0; i < 4; i++) {
      var m = el('div', 'tour-mask');
      document.body.appendChild(m);
      masks.push(m);
    }
    highlight = el('div', 'tour-highlight');
    document.body.appendChild(highlight);
  }

  function removeMasks() {
    masks.forEach(function (m) { m.remove(); });
    masks = [];
    if (highlight) { highlight.remove(); highlight = null; }
  }

  function positionMasks(rect) {
    var pad = 6;
    var t = rect.top - pad,
        l = rect.left - pad,
        w = rect.width + pad * 2,
        h = rect.height + pad * 2,
        vw = window.innerWidth,
        vh = window.innerHeight;

    // top
    masks[0].style.cssText = 'top:0;left:0;width:100%;height:' + Math.max(0, t) + 'px;';
    // bottom
    masks[1].style.cssText = 'top:' + (t + h) + 'px;left:0;width:100%;height:' + Math.max(0, vh - t - h) + 'px;';
    // left
    masks[2].style.cssText = 'top:' + t + 'px;left:0;width:' + Math.max(0, l) + 'px;height:' + h + 'px;';
    // right
    masks[3].style.cssText = 'top:' + t + 'px;left:' + (l + w) + 'px;width:' + Math.max(0, vw - l - w) + 'px;height:' + h + 'px;';

    highlight.style.cssText = 'top:' + t + 'px;left:' + l + 'px;width:' + w + 'px;height:' + h + 'px;';
  }

  function coverAll() {
    masks.forEach(function (m, i) {
      if (i === 0) m.style.cssText = 'top:0;left:0;width:100%;height:100%;';
      else m.style.cssText = 'display:none';
    });
    if (highlight) highlight.style.cssText = 'display:none';
  }

  /* ── Karte positionieren ─────────────────────────────────── */
  function positionCard(target) {
    var cw = 340, ch = card.offsetHeight || 260;
    var vw = window.innerWidth, vh = window.innerHeight;

    if (!target) {
      // Zentriert
      card.style.top = Math.max(16, (vh - ch) / 2) + 'px';
      card.style.left = Math.max(16, (vw - cw) / 2) + 'px';
      card.removeAttribute('data-arrow');
      return;
    }

    var rect = target.getBoundingClientRect();
    var pad = 12;

    // Versuche: rechts, links, unten, oben
    var pos = null;
    if (rect.right + cw + pad + 16 <= vw) {
      pos = { top: Math.min(vh - ch - 16, Math.max(16, rect.top)), left: rect.right + pad, arrow: 'left' };
    } else if (rect.left - cw - pad - 16 >= 0) {
      pos = { top: Math.min(vh - ch - 16, Math.max(16, rect.top)), left: rect.left - cw - pad, arrow: 'right' };
    } else if (rect.bottom + ch + pad + 16 <= vh) {
      pos = { top: rect.bottom + pad, left: Math.min(vw - cw - 16, Math.max(16, rect.left)), arrow: 'top' };
    } else {
      pos = { top: Math.max(16, rect.top - ch - pad), left: Math.min(vw - cw - 16, Math.max(16, rect.left)), arrow: 'bottom' };
    }

    card.style.top = pos.top + 'px';
    card.style.left = pos.left + 'px';
    card.setAttribute('data-arrow', pos.arrow);
  }

  /* ── Karte aufbauen ──────────────────────────────────────── */
  function buildCard() {
    card = el('div', 'tour-card');
    document.body.appendChild(card);
  }

  function renderStep(idx) {
    var step = STEPS[idx];
    var total = STEPS.length;
    var pct = Math.round(((idx) / (total - 1)) * 100);

    card.innerHTML =
      '<div class="tour-card-header">' +
        '<span class="tour-card-icon">' + step.icon + '</span>' +
        '<span class="tour-card-title">' + step.title + '</span>' +
        '<span class="tour-step-badge">' + (idx + 1) + ' / ' + total + '</span>' +
      '</div>' +
      '<div class="tour-progress"><div class="tour-progress-bar" style="width:' + pct + '%"></div></div>' +
      '<div class="tour-card-body">' + step.body + '</div>' +
      '<div class="tour-card-footer">' +
        '<button class="tour-btn tour-btn-skip" id="tourSkip">Tour beenden</button>' +
        '<div class="d-flex gap-2">' +
          (idx > 0 ? '<button class="tour-btn tour-btn-prev" id="tourPrev">Zurück</button>' : '') +
          (step.finish
            ? '<button class="tour-btn tour-btn-next tour-btn-finish" id="tourNext">Fertig 🎉</button>'
            : '<button class="tour-btn tour-btn-next" id="tourNext">Weiter →</button>') +
        '</div>' +
      '</div>';

    card.querySelector('#tourSkip').addEventListener('click', endTour);
    card.querySelector('#tourNext').addEventListener('click', function () {
      if (step.finish) { endTour(); spawnConfetti(); } else { goStep(idx + 1); }
    });
    var prevBtn = card.querySelector('#tourPrev');
    if (prevBtn) prevBtn.addEventListener('click', function () { goStep(idx - 1); });
  }

  /* ── Schritt anzeigen ────────────────────────────────────── */
  function goStep(idx) {
    if (idx < 0 || idx >= STEPS.length) return;
    currentStep = idx;
    card.classList.remove('visible');

    var step = STEPS[idx];
    var target = getTarget(step);

    if (target) {
      target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    setTimeout(function () {
      renderStep(idx);

      if (target) {
        var rect = target.getBoundingClientRect();
        positionMasks(rect);
      } else {
        coverAll();
      }

      // Kurz warten damit offsetHeight stimmt
      requestAnimationFrame(function () {
        positionCard(target);
        card.classList.add('visible');
      });
    }, 120);
  }

  /* ── Tour starten ────────────────────────────────────────── */
  function startTour() {
    if (welcomeModal) { welcomeModal.remove(); welcomeModal = null; }
    if (active) return;
    active = true;
    localStorage.setItem('pflegeos_tour_seen', '1');

    createMasks();
    buildCard();
    coverAll();
    goStep(0);

    document.addEventListener('keydown', keyHandler);
  }

  /* ── Tour beenden ────────────────────────────────────────── */
  function endTour() {
    active = false;
    removeMasks();
    if (card) { card.remove(); card = null; }
    document.removeEventListener('keydown', keyHandler);
  }

  /* ── Tastatur ────────────────────────────────────────────── */
  function keyHandler(e) {
    if (e.key === 'Escape') { endTour(); return; }
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { goStep(currentStep + 1); }
    if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')   { goStep(currentStep - 1); }
  }

  /* ── Welcome-Modal ───────────────────────────────────────── */
  function showWelcome() {
    welcomeModal = el('div', 'tour-welcome');
    welcomeModal.innerHTML =
      '<div class="tour-welcome-inner">' +
        '<div class="tour-welcome-logo">🏥</div>' +
        '<div class="tour-welcome-title">Willkommen in PflegeOS</div>' +
        '<div class="tour-welcome-sub">Möchten Sie eine kurze Führung durch alle Funktionen erhalten? Die Tour zeigt Ihnen Dashboard, Patienten, Touren, Abrechnungen und vieles mehr — in etwa 2 Minuten.</div>' +
        '<button class="tour-welcome-btn-start" id="tourWelcomeStart">Tour starten →</button>' +
        '<button class="tour-welcome-btn-skip" id="tourWelcomeSkip">Überspringen, ich kenne mich aus</button>' +
      '</div>';
    document.body.appendChild(welcomeModal);
    document.getElementById('tourWelcomeStart').addEventListener('click', startTour);
    document.getElementById('tourWelcomeSkip').addEventListener('click', function () {
      localStorage.setItem('pflegeos_tour_seen', '1');
      welcomeModal.remove();
      welcomeModal = null;
    });
  }

  /* ── "Tour starten"-Button in der Navbar befestigen ──────── */
  function attachNavButton() {
    var btn = document.getElementById('tourStartBtn');
    if (btn) {
      btn.addEventListener('click', function () {
        if (active) { endTour(); return; }
        startTour();
      });
    }
  }

  /* ── Init ────────────────────────────────────────────────── */
  function init() {
    attachNavButton();
    // Automatisch beim ersten Login
    if (!localStorage.getItem('pflegeos_tour_seen')) {
      // Kurze Verzögerung damit die Seite fertig geladen ist
      setTimeout(showWelcome, 800);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Fenstergröße → Karte neu positionieren
  window.addEventListener('resize', function () {
    if (!active || !card) return;
    var step = STEPS[currentStep];
    var target = getTarget(step);
    if (target) {
      positionMasks(target.getBoundingClientRect());
    }
    positionCard(target);
  });

})();
