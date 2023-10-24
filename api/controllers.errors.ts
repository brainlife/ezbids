export interface HttpError {
    readonly statusCode: number;
    message: string;
}

export class UnauthorizedHttpError extends Error implements HttpError {
    readonly statusCode = 401;
    constructor(message: string) { super(message); }
}

export class NotFoundHttpError extends Error {
    readonly statusCode = 404;
    constructor(message: string) { super(message) }
}

export class BadRequestHttpError extends Error {
    readonly statuscode = 400;
    constructor(message: string) { super(message) }
}

export class InternalServerHttpError extends Error {
    readonly statusCode = 500;
    constructor(message: string) { super(message) }
}