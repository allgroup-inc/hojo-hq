import { Response, NextFunction } from 'express';
import jwtHandler from '../auth/jwt-handler';
import { AuthRequest, UserRole, AuthenticatedUser } from '../types/user.types';

/**
 * Bearer トークン検証ミドルウェア
 * Authorization: Bearer <token> ヘッダーから JWT を抽出・検証
 * リクエストに認証済みユーザー情報を附与
 */
export const authenticate = (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const authHeader = req.headers.authorization;

    if (!authHeader) {
      return res.status(401).json({
        error: 'Unauthorized',
        message: 'Missing Authorization header',
      });
    }

    const token = jwtHandler.extractToken(authHeader);
    if (!token) {
      return res.status(401).json({
        error: 'Unauthorized',
        message: 'Invalid Authorization format. Use: Bearer <token>',
      });
    }

    const decoded = jwtHandler.verifyToken(token);
    if (!decoded) {
      return res.status(401).json({
        error: 'Unauthorized',
        message: 'Invalid or expired token',
      });
    }

    /**
     * PoC: ロール情報は クエリパラメータ（?role=ADMIN）から取得
     * Phase 1以降: DB クエリで取得に変更
     */
    const userRole = (req.query.role as UserRole) || UserRole.SALES_REP;
    if (!Object.values(UserRole).includes(userRole)) {
      return res.status(400).json({
        error: 'Bad request',
        message: `Invalid role: ${userRole}. Must be one of: ${Object.values(UserRole).join(', ')}`,
      });
    }

    const user: AuthenticatedUser = {
      id: decoded.sub,
      email: decoded.email,
      displayName: decoded.displayName,
      role: userRole,
      iat: decoded.iat,
      exp: decoded.exp,
    };

    req.user = user;
    next();
  } catch (error) {
    console.error('Authentication error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * ロールベースアクセス制御（RBAC）ミドルウェア
 * 指定されたロールのみアクセス許可
 *
 * @param allowedRoles 許可されるロールの配列
 * @example
 * router.get('/admin', authenticate, authorize(UserRole.ADMIN), handler)
 */
export const authorize = (...allowedRoles: UserRole[]) => {
  return (req: AuthRequest, res: Response, next: NextFunction) => {
    if (!req.user) {
      return res.status(401).json({
        error: 'Unauthorized',
        message: 'User not authenticated',
      });
    }

    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({
        error: 'Forbidden',
        message: `Access denied. Required roles: ${allowedRoles.join(', ')}. Your role: ${req.user.role}`,
      });
    }

    next();
  };
};

/**
 * 同一ユーザー確認ミドルウェア（PoC）
 * 自分自身のリソースのみアクセス可能
 * ADMIN ロールは例外（全ユーザーのリソースにアクセス可能）
 *
 * @example
 * router.get('/sales/:repId/schedule', authenticate, authorizeOwnerOrAdmin, handler)
 */
export const authorizeOwnerOrAdmin = (req: AuthRequest, res: Response, next: NextFunction) => {
  if (!req.user) {
    return res.status(401).json({
      error: 'Unauthorized',
      message: 'User not authenticated',
    });
  }

  // URL パラメータまたはリクエストボディから対象ユーザー ID を取得
  const resourceUserId = req.params.repId || req.body.repId;

  if (!resourceUserId) {
    return res.status(400).json({
      error: 'Bad request',
      message: 'Missing repId parameter or in request body',
    });
  }

  // ADMIN はすべてのリソースにアクセス可能、他は自身のリソースのみ
  if (req.user.role !== UserRole.ADMIN && req.user.id !== resourceUserId) {
    return res.status(403).json({
      error: 'Forbidden',
      message: 'Access denied. You can only access your own resources or be an admin.',
    });
  }

  next();
};
