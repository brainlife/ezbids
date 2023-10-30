import { HTTP_STATUS } from "./controllers.utils";

export interface HttpError {
    readonly statusCode: number;
    message: string;
}

export class UnauthorizedHttpError extends Error implements HttpError {
    readonly statusCode = HTTP_STATUS.UNAUTHORIZED
    constructor(message: string) { super(message); }
}

export class NotFoundHttpError extends Error {
    readonly statusCode = HTTP_STATUS.NOT_FOUND
    constructor(message: string) { super(message) }
}

export class BadRequestHttpError extends Error {
    readonly statuscode = HTTP_STATUS.BAD_REQUEST
    constructor(message: string) { super(message) }
}

export class InternalServerHttpError extends Error {
    readonly statusCode = HTTP_STATUS.INTERNAL_SERVER_ERROR
    constructor(message: string) { super(message) }
}