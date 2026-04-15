'use client';

import * as React from 'react';

/**
 * EmailBodyFrame — renders untrusted email HTML inside a Shadow DOM.
 *
 * Shadow DOM gives us:
 *   - Style isolation: the email's own <style> / inline styles can't leak
 *     into the host app (that was restyling the header, logo, spacing).
 *   - Natural layout: unlike an iframe, the shadow tree participates in
 *     the parent document's block flow. No height measurement, no inner
 *     scrollbar, no fixed viewport — the card grows to fit the content
 *     and fills the pane width like any normal div.
 *
 * We also strip <script>, <iframe>, <object>, <embed>, <link rel="import">
 * and on* event handlers before mounting so the email can't run code.
 */
export function EmailBodyFrame({ html }: { html: string }) {
  const hostRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const shadow = host.shadowRoot ?? host.attachShadow({ mode: 'open' });

    // Parse the email HTML in a detached document so <script>/<style>/<link>
    // don't execute or fetch at parse time.
    const parsed = new DOMParser().parseFromString(
      `<!doctype html><html><body>${html}</body></html>`,
      'text/html',
    );

    sanitize(parsed);

    // Build the shadow content: a base reset + whatever the email brought.
    // The email's own <style> blocks live inside the shadow root, so they
    // apply to the email and nothing else.
    const wrapper = document.createElement('div');
    wrapper.className = 'email-root';

    // Move parsed nodes into the wrapper.
    while (parsed.body.firstChild) {
      wrapper.appendChild(parsed.body.firstChild);
    }

    const reset = document.createElement('style');
    reset.textContent = `
      :host {
        display: block;
        width: 100%;
        color: #1f2937;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
          Oxygen, Ubuntu, Cantarell, sans-serif;
        font-size: 14px;
        line-height: 1.55;
      }
      .email-root { all: initial; display: block; }
      .email-root,
      .email-root * {
        font-family: inherit;
        box-sizing: border-box;
        max-width: 100%;
      }
      .email-root img { max-width: 100%; height: auto; }
      .email-root a { color: #2563eb; text-decoration: underline; }
      .email-root table { max-width: 100%; }
      .email-root pre, .email-root code {
        white-space: pre-wrap;
        word-break: break-word;
      }
      .email-root blockquote {
        margin: 0.5em 0;
        padding-left: 0.75em;
        border-left: 3px solid #e5e7eb;
        color: #6b7280;
      }
    `;

    // Dark-mode tweak — picks up whenever the host app is in .dark.
    if (document.documentElement.classList.contains('dark')) {
      reset.textContent += `
        :host { color: #e5e7eb; }
        .email-root blockquote { color: #9ca3af; border-left-color: #374151; }
      `;
    }

    // Replace existing shadow content.
    shadow.replaceChildren(reset, wrapper);

    // Force all <a> targets to _blank so clicking a link in a sanitized
    // email opens a new tab instead of replacing the app.
    wrapper.querySelectorAll('a[href]').forEach((a) => {
      a.setAttribute('target', '_blank');
      a.setAttribute('rel', 'noopener noreferrer');
    });
  }, [html]);

  return <div ref={hostRef} className="w-full" />;
}

/**
 * Remove scripts, event handlers, and anything that could fetch or execute
 * before the nodes get mounted. Keeps <style> because that's scoped by
 * the shadow root.
 */
function sanitize(doc: Document) {
  const dropTags = ['SCRIPT', 'IFRAME', 'OBJECT', 'EMBED', 'META', 'LINK'];
  doc.querySelectorAll(dropTags.join(',')).forEach((el) => el.remove());

  // Strip on* handlers, javascript: URLs, and srcdoc.
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_ELEMENT);
  const suspicious: Element[] = [];
  let current: Node | null = walker.currentNode;
  while (current) {
    if (current instanceof Element) suspicious.push(current);
    current = walker.nextNode();
  }

  for (const el of suspicious) {
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase();
      const value = attr.value.trim().toLowerCase();
      if (name.startsWith('on')) {
        el.removeAttribute(attr.name);
      } else if (
        (name === 'href' || name === 'src' || name === 'xlink:href') &&
        value.startsWith('javascript:')
      ) {
        el.removeAttribute(attr.name);
      } else if (name === 'srcdoc') {
        el.removeAttribute(attr.name);
      }
    }
  }
}
