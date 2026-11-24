import { reactive } from 'vue';

/* Links to other sites open in a dialog over the app (ExternalPageDialog, mounted once in App.vue)
   instead of a new window or tab. Hosts on this list allow being framed (no X-Frame-Options or CSP
   frame-ancestors, checked with `curl -sI`), so they are shown in an iframe; any other host (GitHub,
   nature.com, nsf.gov send DENY / SAMEORIGIN) gets a dialog that says so and opens it in a new tab
   only when the user confirms, since a browser has no way to show those inside the page. */
export const FRAMEABLE_HOSTS = ['brainlife.io', 'readthedocs.io', 'openneuro.org', 'hedtags.org', 'grantome.com'];

export interface ExternalPage {
    url: string;
    title: string;
    note: string;
}

export const externalPage = reactive<ExternalPage>({ url: '', title: '', note: '' });

export function canFrame(url: string): boolean {
    try {
        const u = new URL(url, window.location.href);
        if (u.protocol !== 'https:' && u.origin !== window.location.origin) return false;
        if (u.origin === window.location.origin) return true;
        return FRAMEABLE_HOSTS.some((h) => u.hostname === h || u.hostname.endsWith(`.${h}`));
    } catch {
        return false;
    }
}

export function openExternal(url: string, opts: { title?: string; note?: string } = {}) {
    externalPage.url = url;
    externalPage.title = opts.title || '';
    externalPage.note = opts.note || '';
}

export function closeExternal() {
    externalPage.url = '';
    externalPage.title = '';
    externalPage.note = '';
}

/* Document-level click handler: a plain left click on a link to another site opens it in the dialog.
   Links inside the app (same origin, under the app's base path), downloads and modified clicks
   (cmd/ctrl/shift: the user asked for a tab) are left alone. */
export function interceptExternalLinks(e: MouseEvent) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
    if (!a || a.hasAttribute('download') || a.dataset.external === 'allow') return;
    let url: URL;
    try {
        url = new URL(a.href, window.location.href);
    } catch {
        return;
    }
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return;
    const base = import.meta.env.BASE_URL || '/';
    if (url.origin === window.location.origin && url.pathname.startsWith(base)) return;
    e.preventDefault();
    const text = (a.getAttribute('aria-label') || a.textContent || '').trim();
    // a bare URL or a one-word "here" makes a poor title; the dialog then shows the host
    openExternal(url.href, { title: /^https?:|^here$/i.test(text) ? '' : text });
}
