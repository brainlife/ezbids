'use strict';

import { HydratedDocument, Types, UpdateQuery } from 'mongoose';
import { IEzBIDS, ISession } from '../models';

/** Query for finding sessions (e.g. by status). */
export interface SessionQuery {
    status?: { $in?: string[] };
}

export type ISessionWithId = ISession & { _id: string };
export type ISessionReturn = ISessionWithId | HydratedDocument<ISession>;

export type IEzBIDSWithId = IEzBIDS & { _id: string };
export type IEzBIDSReturn = IEzBIDSWithId | HydratedDocument<IEzBIDS>;

export interface ISessionStore {
    findById(id: string): Promise<ISessionReturn | null>;
    find(query: SessionQuery): Promise<ISessionReturn[]>;
    create(data: Partial<ISession>): Promise<ISessionReturn>;
    save(session: ISessionReturn): Promise<ISessionReturn>;
}

export interface IEzBIDSStore {
    findOneBySessionId(sessionId: string | Types.ObjectId): Promise<IEzBIDSReturn | null>;
    findOneAndUpdate(sessionId: string | Types.ObjectId, update: UpdateQuery<Partial<IEzBIDS>>): Promise<void>;
    create(data: Omit<IEzBIDS, 'create_date' | 'update_date' | 'updated'>): Promise<IEzBIDSReturn>;
}
