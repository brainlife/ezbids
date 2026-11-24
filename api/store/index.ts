'use strict';

import * as config from '../config';
import type { ISessionStore, IEzBIDSStore } from './types';
import { sessionStore as mongoSessionStore, ezbidsStore as mongoEzBIDSStore } from './mongo.store';

/*
 * The desktop store (electron-store, which imports the `electron` package) is loaded only when IS_ELECTRON
 * is true, so the web API and handler (Docker, MongoDB) never load Electron code.
 */
// eslint-disable-next-line @typescript-eslint/no-var-requires
const electronStore = (): typeof import('./electron.store') => require('./electron.store');

/** Single session store: MongoDB when !isElectron, electron-store when isElectron. */
export const sessionStore: ISessionStore = config.isElectron ? electronStore().sessionStore : mongoSessionStore;

/** Single ezBIDS store: MongoDB when !isElectron, electron-store when isElectron. */
export const ezbidsStore: IEzBIDSStore = config.isElectron ? electronStore().ezbidsStore : mongoEzBIDSStore;

export type { ISessionStore, IEzBIDSStore, ISessionReturn as SessionDoc, SessionQuery } from './types';
