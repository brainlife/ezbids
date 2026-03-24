'use strict';

import * as config from '../config';
import type { ISessionStore, IEzBIDSStore } from './types';
import { sessionStore as mongoSessionStore, ezbidsStore as mongoEzBIDSStore } from './mongo.store';

let _sessionStore: ISessionStore;
let _ezbidsStore: IEzBIDSStore;

if (config.isElectron) {
    // Dynamic import to avoid loading electron-store (and electron) in non-electron environments
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { sessionStore: electronSessionStore, ezbidsStore: electronEzBIDSStore } = require('./electron.store');
    _sessionStore = electronSessionStore;
    _ezbidsStore = electronEzBIDSStore;
} else {
    _sessionStore = mongoSessionStore;
    _ezbidsStore = mongoEzBIDSStore;
}

export const sessionStore: ISessionStore = _sessionStore;
export const ezbidsStore: IEzBIDSStore = _ezbidsStore;

export type { ISessionStore, IEzBIDSStore, ISessionReturn as SessionDoc, SessionQuery } from './types';
