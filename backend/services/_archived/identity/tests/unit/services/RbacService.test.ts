import { describe, it, expect, beforeEach } from 'vitest';
import { RbacService } from '../../../src/services/RbacService.js';
import type { UserRole } from '../../../src/domain/User.js';

describe('RbacService', () => {
  let rbac: RbacService;

  beforeEach(() => {
    rbac = new RbacService();
  });

  it('should allow SUPER_ADMIN to access any resource', () => {
    const roles: UserRole[] = ['DEPT_ADMIN', 'VC', 'REGISTRAR', 'DEAN', 'HOD', 'STAFF'];
    for (const required of roles) {
      expect(rbac.canAccess('SUPER_ADMIN', [required])).toBe(true);
    }
  });

  it('should allow VC to access VC-level resources', () => {
    expect(rbac.canAccess('VC', ['VC'])).toBe(true);
  });

  it('should deny STAFF from accessing admin resources', () => {
    expect(rbac.canAccess('STAFF', ['SUPER_ADMIN'])).toBe(false);
    expect(rbac.canAccess('STAFF', ['DEPT_ADMIN'])).toBe(false);
    expect(rbac.canAccess('STAFF', ['VC'])).toBe(false);
    expect(rbac.canAccess('STAFF', ['DEAN'])).toBe(false);
    expect(rbac.canAccess('STAFF', ['HOD'])).toBe(false);
  });

  it('should allow access when user has required role in hierarchy', () => {
    // DEPT_ADMIN (80) > VC (70) > DEAN (60) > HOD (50) > STAFF (10)
    expect(rbac.canAccess('DEPT_ADMIN', ['VC'])).toBe(true);
    expect(rbac.canAccess('DEPT_ADMIN', ['DEAN'])).toBe(true);
    expect(rbac.canAccess('VC', ['DEAN'])).toBe(true);
    expect(rbac.canAccess('DEAN', ['HOD'])).toBe(true);
    expect(rbac.canAccess('HOD', ['STAFF'])).toBe(true);
  });

  it('should deny access when user role is insufficient', () => {
    expect(rbac.canAccess('STAFF', ['REGISTRAR'])).toBe(false);
    expect(rbac.canAccess('HOD', ['DEAN'])).toBe(false);
    expect(rbac.canAccess('DEAN', ['REGISTRAR'])).toBe(false);
    expect(rbac.canAccess('DEAN', ['VC'])).toBe(false);
    expect(rbac.canAccess('VC', ['DEPT_ADMIN'])).toBe(false);
    expect(rbac.canAccess('REGISTRAR', ['DEPT_ADMIN'])).toBe(false);
  });

  it('should support multiple allowed roles (any-of semantics)', () => {
    // If user role matches one of the required roles exactly
    expect(rbac.canAccess('DEAN', ['HOD', 'DEAN', 'VC'])).toBe(true);
    expect(rbac.canAccess('STAFF', ['STAFF', 'HOD'])).toBe(true);
  });
});
