/**
 * Other sites open inside the main window, never in a new window.
 *
 * The renderer shows them in a dialog with a <webview> (ui/src/components/dialogs/ExternalPageDialog.vue).
 * Here the main process:
 * - denies every new window from the app and sends https URLs to that dialog instead (IN_APP_OPEN_CHANNEL);
 * - keeps the app window on the app (file://, or the localhost dev server / API for downloads);
 * - locks each <webview> guest down: no preload, no Node, context isolation, sandbox, https only;
 * - loads a guest's own pop-ups in the same guest.
 */
import type { BrowserWindow, Event, WebPreferences } from 'electron';

export const IN_APP_OPEN_CHANNEL = 'ezbids:open-in-app';

const isHttps = (url: string | undefined): boolean => {
    try {
        return !!url && new URL(url).protocol === 'https:';
    } catch {
        return false;
    }
};

/** The app itself: the packaged index.html, the vite dev server and the local API (downloads). */
const isAppUrl = (url: string): boolean => {
    try {
        const u = new URL(url);
        return u.protocol === 'file:' || (u.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(u.hostname));
    } catch {
        return false;
    }
};

export function enableInAppBrowsing(win: BrowserWindow): void {
    const app = win.webContents;
    const toDialog = (url: string) => {
        if (isHttps(url)) app.send(IN_APP_OPEN_CHANNEL, url);
    };

    app.setWindowOpenHandler(({ url }) => {
        toDialog(url);
        return { action: 'deny' };
    });

    app.on('will-navigate', (event, url) => {
        if (isAppUrl(url)) return;
        event.preventDefault();
        toDialog(url);
    });

    app.on('will-attach-webview', (event, webPreferences: WebPreferences, params) => {
        delete webPreferences.preload;
        webPreferences.nodeIntegration = false;
        webPreferences.nodeIntegrationInSubFrames = false;
        webPreferences.contextIsolation = true;
        webPreferences.sandbox = true;
        webPreferences.webSecurity = true;
        if (!isHttps(params.src)) event.preventDefault();
    });

    app.on('did-attach-webview', (_event, guest) => {
        guest.setWindowOpenHandler(({ url }) => {
            if (isHttps(url)) void guest.loadURL(url);
            return { action: 'deny' };
        });
        const httpsOnly = (event: Event, url: string) => {
            if (!isHttps(url)) event.preventDefault();
        };
        guest.on('will-navigate', httpsOnly);
        guest.on('will-redirect', httpsOnly);
    });
}
