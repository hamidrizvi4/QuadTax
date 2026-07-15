// QuadTax website – custom JavaScript
// Adds lightweight client-side form validation and alert auto-dismiss.

document.addEventListener('DOMContentLoaded', function () {
  // Disable submission until fields are valid (visual only — wire to backend later)
  document.querySelectorAll('form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (!form.checkValidity()) {
        e.preventDefault();
        e.stopPropagation();
      }
      form.classList.add('was-validated');
    });
  });

  // Auto-hide any alert messages after 5 seconds
  setTimeout(function () {
    document.querySelectorAll('.alert').forEach(function (alert) {
      if (window.bootstrap && bootstrap.Alert) {
        new bootstrap.Alert(alert).close();
      }
    });
  }, 5000);
});
