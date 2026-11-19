(function () {
  var doc = document.documentElement;
  doc.classList.add('js');

  // Mobile menu
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!open));
      nav.classList.toggle('open', !open);
    });
  }

  // Dropdowns: click or keyboard, Escape closes, click outside closes
  var submenuToggles = document.querySelectorAll('.submenu-toggle');
  function closeAll(except) {
    submenuToggles.forEach(function (btn) {
      if (btn !== except) btn.setAttribute('aria-expanded', 'false');
    });
  }
  submenuToggles.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var open = btn.getAttribute('aria-expanded') === 'true';
      closeAll(btn);
      btn.setAttribute('aria-expanded', String(!open));
    });
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Escape') return;
    var open = document.querySelector('.submenu-toggle[aria-expanded="true"]');
    if (open) {
      open.setAttribute('aria-expanded', 'false');
      open.focus();
    }
  });
  document.addEventListener('click', function (ev) {
    if (!ev.target.closest('.has-menu')) closeAll(null);
  });

  // Contact form: preselect from ?topic= and ?product=, send through the visitor's email program
  var form = document.getElementById('contact-form');
  if (!form) return;
  var params = new URLSearchParams(window.location.search);
  ['topic', 'product'].forEach(function (key) {
    var value = params.get(key);
    var field = form.elements[key];
    if (!value || !field) return;
    for (var i = 0; i < field.options.length; i++) {
      if (field.options[i].value === value) field.value = value;
    }
  });
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    if (!form.reportValidity()) return;
    var f = form.elements;
    var topic = f.topic.options[f.topic.selectedIndex].text;
    var product = f.product.value ? f.product.options[f.product.selectedIndex].text : 'Not sure yet';
    var subject = topic + (f.product.value ? ': ' + product : '');
    var body = [
      f.message.value,
      '',
      'Name: ' + f.name.value,
      'Company: ' + f.company.value,
      'Email: ' + f.email.value,
      'Phone: ' + f.phone.value,
      'Product: ' + product
    ].join('\n');
    window.location.href = 'mailto:' + form.getAttribute('data-to') +
      '?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
  });
})();
