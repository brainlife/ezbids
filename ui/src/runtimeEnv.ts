/*
 * window.env holds the settings the UI reads at run time (API_HOST, IS_ELECTRON, BRAINLIFE_AUTHENTICATION).
 * The desktop app's preload script provides it, and so does public/runtime-env.js written by
 * ui/docker-entrypoint.sh. A web build served without runtime-env.js (e.g. a static `vite build`
 * deployment) falls back to the build-time variables the web UI used before: VITE_APIHOST and
 * VITE_BRAINLIFE_AUTHENTICATION. Import this module before anything that reads window.env.
 */
if (!window.env) {
    window.env = {
        API_HOST: import.meta.env.VITE_APIHOST || '/api/ezbids',
        IS_ELECTRON: 'false',
        BRAINLIFE_AUTHENTICATION: import.meta.env.VITE_BRAINLIFE_AUTHENTICATION === 'true' ? 'true' : 'false',
    };
}

export {};
