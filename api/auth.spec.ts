describe('api/auth', () => {
    const keyPath = (filename: string) => `${__dirname}/${filename}`;

    afterEach(() => {
        jest.resetModules();
        jest.clearAllMocks();
    });

    function loadAuthModule(opts: {
        authentication: boolean;
        keyFiles?: Record<string, string>;
    }): {
        auth: typeof import('./auth');
        jwtVerifyMock: jest.Mock;
        jwtSignMock: jest.Mock;
        expressjwtMock: jest.Mock;
    } {
        const files = opts.keyFiles ?? {};
        const jwtVerifyMock = jest.fn().mockReturnValue({ sessionId: 'sess-1' });
        const jwtSignMock = jest.fn().mockReturnValue('token-123');
        const expressjwtMock = jest.fn().mockReturnValue('jwt-middleware');

        jest.doMock('./config', () => ({
            authentication: opts.authentication,
        }));
        jest.doMock('express-jwt', () => ({
            expressjwt: expressjwtMock,
        }));
        jest.doMock('jsonwebtoken', () => ({
            verify: jwtVerifyMock,
            sign: jwtSignMock,
        }));
        jest.doMock('fs', () => {
            const actualFs = jest.requireActual('fs');
            return {
                ...actualFs,
                existsSync: jest.fn((p: string) => Object.prototype.hasOwnProperty.call(files, p)),
                readFileSync: jest.fn((p: string) => files[p]),
            };
        });

        const auth = require('./auth') as typeof import('./auth');
        return { auth, jwtVerifyMock, jwtSignMock, expressjwtMock };
    }

    it('validateWithJWTConfig returns pass-through middleware when auth is disabled', () => {
        const { auth, expressjwtMock } = loadAuthModule({ authentication: false });
        const req: { auth?: { sub: number } } = {};
        const next = jest.fn();

        const mw = auth.validateWithJWTConfig();
        (mw as (req: unknown, res: unknown, next: () => void) => void)(req, {}, next);

        expect(req.auth).toEqual({ sub: 0 });
        expect(next).toHaveBeenCalledTimes(1);
        expect(expressjwtMock).not.toHaveBeenCalled();
    });

    it('validateWithJWTConfig delegates to expressjwt when auth is enabled', () => {
        const { auth, expressjwtMock } = loadAuthModule({
            authentication: true,
            keyFiles: {
                [keyPath('auth.pub')]: 'PUBLICKEY',
            },
        });

        const result = auth.validateWithJWTConfig({ credentialsRequired: false } as never);

        expect(expressjwtMock).toHaveBeenCalledWith({
            secret: 'PUBLICKEY',
            algorithms: ['RS256'],
            credentialsRequired: false,
        });
        expect(result).toBe('jwt-middleware');
    });

    it('verifyJWT returns undefined for missing token', () => {
        const { auth, jwtVerifyMock } = loadAuthModule({ authentication: false });
        expect(auth.verifyJWT(undefined)).toBeUndefined();
        expect(jwtVerifyMock).not.toHaveBeenCalled();
    });

    it('verifyJWT uses HS256 placeholder key when auth is disabled', () => {
        const { auth, jwtVerifyMock } = loadAuthModule({ authentication: false });
        auth.verifyJWT('abc.def');
        expect(jwtVerifyMock).toHaveBeenCalledWith('abc.def', 'placeholder-key', { algorithms: ['HS256'] });
    });

    it('verifyJWT uses RS256 public key when auth is enabled', () => {
        const { auth, jwtVerifyMock } = loadAuthModule({
            authentication: true,
            keyFiles: {
                [keyPath('auth.pub')]: 'PUBLICKEY',
                [keyPath('ezbids.pub')]: 'EZPUB',
            },
        });
        auth.verifyJWT('token-x');
        expect(jwtVerifyMock).toHaveBeenCalledWith('token-x', 'EZPUB', { algorithms: ['RS256'] });
    });

    it('verifyJWT throws when auth enabled and ezbids public key is missing', () => {
        const { auth } = loadAuthModule({
            authentication: true,
            keyFiles: {
                [keyPath('auth.pub')]: 'PUBLICKEY',
            },
        });
        expect(() => auth.verifyJWT('token-x')).toThrow('missing ezbids public key');
    });

    it('signJWT uses HS256 placeholder key and merges overrides when auth disabled', () => {
        const { auth, jwtSignMock } = loadAuthModule({ authentication: false });
        auth.signJWT({ sessionId: 's1' }, { expiresIn: '30s' });
        expect(jwtSignMock).toHaveBeenCalledWith(
            { sessionId: 's1' },
            'placeholder-key',
            expect.objectContaining({ algorithm: 'HS256', expiresIn: '30s' })
        );
    });

    it('signJWT uses RS256 private key when auth enabled', () => {
        const { auth, jwtSignMock } = loadAuthModule({
            authentication: true,
            keyFiles: {
                [keyPath('auth.pub')]: 'PUBLICKEY',
                [keyPath('ezbids.key')]: 'PRIVATEKEY',
            },
        });
        auth.signJWT({ sessionId: 's2' });
        expect(jwtSignMock).toHaveBeenCalledWith(
            { sessionId: 's2' },
            'PRIVATEKEY',
            expect.objectContaining({ algorithm: 'RS256', expiresIn: '600s' })
        );
    });

    it('signJWT throws when auth enabled and private key missing', () => {
        const { auth } = loadAuthModule({
            authentication: true,
            keyFiles: {
                [keyPath('auth.pub')]: 'PUBLICKEY',
            },
        });
        expect(() => auth.signJWT({ sessionId: 's2' })).toThrow('missing ezbids private key');
    });
});
