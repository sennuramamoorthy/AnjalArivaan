import type { UserRole } from '../domain/User.js';

export const ROLE_LEVEL: Record<UserRole, number> = {
  SUPER_ADMIN: 100,
  DEPT_ADMIN: 80,
  VC: 70,
  REGISTRAR: 70,
  DEAN: 60,
  HOD: 50,
  STAFF: 10,
};

export class RbacService {
  /**
   * Returns true if the user's role is in the list of required roles,
   * OR if the user's role level exceeds all required role levels
   * (i.e. SUPER_ADMIN can always access).
   */
  canAccess(userRole: UserRole, requiredRoles: UserRole[]): boolean {
    if (requiredRoles.length === 0) return true;

    // Direct match
    if (requiredRoles.includes(userRole)) return true;

    // Hierarchy: user's level must meet or exceed ALL required roles' levels
    const userLevel = ROLE_LEVEL[userRole];
    const maxRequiredLevel = Math.max(...requiredRoles.map((r) => ROLE_LEVEL[r]));

    return userLevel >= maxRequiredLevel;
  }
}
