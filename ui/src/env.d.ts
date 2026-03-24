/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_APIHOST: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}

declare module '*.png' {
    const value: string;
    export default value;
}

declare module '*.svg' {
    const value: string;
    export default value;
}
