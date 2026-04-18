/* DocSync — client-side Lunr.js search */
(function () {
  'use strict';

  var idx = null;
  var docs = [];

  function getRoot() {
    return document.documentElement.dataset.root || '';
  }

  function loadIndex(callback) {
    if (idx) { callback(); return; }
    fetch(getRoot() + 'search-index.json')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        docs = data;
        idx = lunr(function () {
          this.ref('id');
          this.field('title', { boost: 10 });
          this.field('tags', { boost: 5 });
          this.field('body');
          data.forEach(function (d) { this.add(d); }, this);
        });
        callback();
      })
      .catch(function (e) {
        console.warn('DocSync search: failed to load index', e);
        var resultsEl = document.getElementById('search-results') ||
                        document.getElementById('results');
        if (resultsEl) {
          var p = document.createElement('p');
          p.style.color = 'var(--text-muted)';
          p.textContent = 'Search index unavailable. Try running: docsync sync';
          resultsEl.textContent = '';
          resultsEl.appendChild(p);
        }
      });
  }

  function renderResults(results, container) {
    if (!results.length) {
      container.innerHTML = '<p style="color:var(--text-muted)">No results found.</p>';
      return;
    }
    var html = '<ul class="entry-list">';
    results.slice(0, 20).forEach(function (r) {
      var doc = docs[r.ref];
      if (!doc) return;
      html += '<li><a href="' + getRoot() + doc.url + '">' +
        '<div><div class="entry-title">' + doc.title + '</div>' +
        '<div class="entry-desc">' + doc.source + '</div></div>' +
        '<div class="entry-meta">' + (doc.tags || '') + '</div>' +
        '</a></li>';
    });
    html += '</ul>';
    container.innerHTML = html;
  }

  // Header search — redirect to search page
  document.addEventListener('DOMContentLoaded', function () {
    var headerInput = document.getElementById('search-input');
    if (headerInput) {
      headerInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && this.value.trim()) {
          window.location.href = getRoot() + 'search.html?q=' + encodeURIComponent(this.value.trim());
        }
      });
    }

    // Full search page
    var pageInput = document.getElementById('page-search-input');
    var resultsEl = document.getElementById('search-results');
    if (!pageInput || !resultsEl) return;

    // Pre-fill from URL param
    var params = new URLSearchParams(window.location.search);
    var q = params.get('q') || '';
    if (q) {
      pageInput.value = q;
      loadIndex(function () { doSearch(q); });
    }

    var debounceTimer = null;
    pageInput.addEventListener('input', function () {
      var query = this.value.trim();
      clearTimeout(debounceTimer);
      if (query.length < 2) { resultsEl.innerHTML = ''; return; }
      debounceTimer = setTimeout(function () {
        loadIndex(function () { doSearch(query); });
      }, 200);
    });

    function doSearch(query) {
      try {
        var results = idx.search(query + '~1');  // fuzzy
        renderResults(results, resultsEl);
      } catch (e) {
        resultsEl.innerHTML = '<p style="color:var(--text-muted)">Search error: ' + e.message + '</p>';
      }
    }
  });
})();
