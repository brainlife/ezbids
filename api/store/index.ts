'use strict';

import * as config from '../config';
import type { ISessionStore, IEzBIDSStore } from './types';
import { sessionStore as mongoSessionStore, ezbidsStore as mongoEzBIDSStore } from './mongo.store';
import { sessionStore as electronSessionStore, ezbidsStore as electronEzBIDSStore } from './electron.store';

/** Single session store: MongoDB when !isElectron, electron-store when isElectron. */
export const sessionStore: ISessionStore = config.isElectron ? electronSessionStore : mongoSessionStore;

/** Single ezBIDS store: MongoDB when !isElectron, electron-store when isElectron. */
export const ezbidsStore: IEzBIDSStore = config.isElectron ? electronEzBIDSStore : mongoEzBIDSStore;

export type { ISessionStore, IEzBIDSStore, ISessionReturn as SessionDoc, SessionQuery } from './types';
