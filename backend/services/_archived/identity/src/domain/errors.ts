export class AuthError extends Error {
  constructor(
    message: string,
    public readonly code: string,
  ) {
    super(message);
    this.name = 'AuthError';
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class InvalidCredentialsError extends AuthError {
  constructor(message = 'Invalid credentials') {
    super(message, 'INVALID_CREDENTIALS');
    this.name = 'InvalidCredentialsError';
  }
}

export class UserAlreadyExistsError extends AuthError {
  constructor(message = 'User already exists') {
    super(message, 'USER_ALREADY_EXISTS');
    this.name = 'UserAlreadyExistsError';
  }
}

export class MfaRequiredError extends AuthError {
  constructor(message = 'MFA code required') {
    super(message, 'MFA_REQUIRED');
    this.name = 'MfaRequiredError';
  }
}

export class InvalidMfaCodeError extends AuthError {
  constructor(message = 'Invalid MFA code') {
    super(message, 'INVALID_MFA_CODE');
    this.name = 'InvalidMfaCodeError';
  }
}

export class TokenExpiredError extends AuthError {
  constructor(message = 'Token has expired') {
    super(message, 'TOKEN_EXPIRED');
    this.name = 'TokenExpiredError';
  }
}

export class TokenInvalidError extends AuthError {
  constructor(message = 'Token is invalid') {
    super(message, 'TOKEN_INVALID');
    this.name = 'TokenInvalidError';
  }
}

export class UnauthorizedError extends AuthError {
  constructor(message = 'Unauthorized') {
    super(message, 'UNAUTHORIZED');
    this.name = 'UnauthorizedError';
  }
}

export class ForbiddenError extends AuthError {
  constructor(message = 'Forbidden') {
    super(message, 'FORBIDDEN');
    this.name = 'ForbiddenError';
  }
}

export class ValidationError extends AuthError {
  constructor(message: string) {
    super(message, 'VALIDATION_ERROR');
    this.name = 'ValidationError';
  }
}

export class MfaDisabledError extends AuthError {
  constructor(message = 'MFA is globally disabled') {
    super(message, 'MFA_DISABLED');
    this.name = 'MfaDisabledError';
  }
}
