/* PostHog analytics – shared across all pages.
   posthog-config.js must load first and set window.POSTHOG_KEY and window.POSTHOG_HOST. */
(function () {
  var key = window.POSTHOG_KEY;
  var host = window.POSTHOG_HOST;
  if (!key || !host) return; // config not loaded, skip analytics

  // Initialize PostHog
  !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey getNextSurveyStep identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
  posthog.init(key, {
    api_host: host,
    defaults: '2026-01-30'
  });

  document.addEventListener('click', function (event) {
    var target = event.target;

    // Project card clicks (index.html)
    var card = target.closest('a.card');
    if (card) {
      var heading = card.querySelector('h2');
      posthog.capture('project_card_clicked', {
        project_title: heading ? heading.innerText.trim() : null,
        project_url: card.getAttribute('href')
      });
      return;
    }

    // Social link clicks (header + footer, all pages)
    var socialBtn = target.closest('a.social-btn');
    if (socialBtn) {
      var platform = null;
      if (socialBtn.classList.contains('social-btn--linkedin')) platform = 'linkedin';
      else if (socialBtn.classList.contains('social-btn--x')) platform = 'x';
      else if (socialBtn.classList.contains('social-btn--youtube')) platform = 'youtube';
      var navEl = socialBtn.closest('nav');
      var loc = navEl && navEl.classList.contains('social-nav--footer') ? 'footer' : 'header';
      posthog.capture('social_link_clicked', {
        platform: platform,
        location: loc,
        href: socialBtn.getAttribute('href')
      });
      return;
    }

    // Back link clicks (project pages)
    var backLink = target.closest('a.back-link');
    if (backLink) {
      posthog.capture('back_link_clicked', {
        page_title: document.title
      });
      return;
    }

    // External link clicks within project page content (file-link class, opens in new tab)
    var fileLink = target.closest('a.file-link');
    if (fileLink) {
      posthog.capture('external_link_clicked', {
        href: fileLink.getAttribute('href'),
        link_text: fileLink.innerText.trim(),
        page_title: document.title
      });
      return;
    }

    // Image lightbox open (pages that have the lightbox widget)
    if (target instanceof HTMLImageElement &&
        target.closest('.media-figure, .media-item, .hero-media-figure') &&
        !target.closest('a')) {
      posthog.capture('image_lightbox_opened', {
        image_src: target.getAttribute('src'),
        image_alt: target.getAttribute('alt') || null,
        page_title: document.title
      });
    }

    // Image lightbox close (close button or backdrop click)
    if (target.closest('.image-lightbox__close') ||
        (target.classList && target.classList.contains('image-lightbox') && target.id === 'image-lightbox')) {
      posthog.capture('image_lightbox_closed', {
        page_title: document.title
      });
    }
  });

  // Lightbox close via Escape key
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      var lightbox = document.getElementById('image-lightbox');
      if (lightbox && lightbox.classList.contains('is-open')) {
        posthog.capture('image_lightbox_closed', {
          page_title: document.title,
          close_method: 'escape_key'
        });
      }
    }
  });

  // YouTube embed clicked (approximated via iframe focus steal on window blur)
  window.addEventListener('blur', function () {
    var active = document.activeElement;
    if (active && active.tagName === 'IFRAME' && active.closest('.embed-wrap')) {
      posthog.capture('youtube_embed_clicked', {
        video_title: active.getAttribute('title') || null,
        video_src: active.getAttribute('src') || null,
        page_title: document.title
      });
    }
  });

  // Scroll depth tracking (50% and 100% milestones, project pages only)
  (function () {
    var milestones = [50, 100];
    var reached = {};
    var ticking = false;

    function checkScrollDepth() {
      var scrollTop = window.scrollY || document.documentElement.scrollTop;
      var docHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (docHeight <= 0) return;
      var pct = Math.round((scrollTop / docHeight) * 100);
      for (var i = 0; i < milestones.length; i++) {
        var m = milestones[i];
        if (!reached[m] && pct >= m) {
          reached[m] = true;
          posthog.capture('scroll_depth_reached', {
            depth_percent: m,
            page_title: document.title
          });
        }
      }
    }

    window.addEventListener('scroll', function () {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(function () {
          checkScrollDepth();
          ticking = false;
        });
      }
    }, { passive: true });
  })();
})();
