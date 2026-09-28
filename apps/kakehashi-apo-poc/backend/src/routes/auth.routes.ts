import express, { Router, Request, Response } from 'express';
import passport from '../auth/passport-strategy';
import jwtHandler from '../auth/jwt-handler';

const router = Router();

/**
 * GET /auth/login
 * Azure AD ログイン開始
 */
router.get(
  '/login',
  passport.authenticate('azuread-openidconnect', {
    session: false,
  })
);

/**
 * GET /auth/callback
 * Azure AD コールバック → JWT トークン発行
 */
router.get(
  '/callback',
  passport.authenticate('azuread-openidconnect', {
    session: false,
    failureRedirect: '/login-error',
  }),
  (req: Request, res: Response) => {
    // req.user は Passport により設定された UserProfile
    if (!req.user) {
      return res.status(401).json({ error: 'Authentication failed' });
    }

    const user = req.user as any;
    const token = jwtHandler.generateToken({
      id: user.id,
      displayName: user.displayName,
      email: user.email,
    });

    // PoC: トークンをレスポンスで返却
    // 本番環境ではセキュアクッキー + リダイレクトに変更
    res.json({
      status: 'authenticated',
      accessToken: token,
      user: {
        id: user.id,
        email: user.email,
        displayName: user.displayName,
      },
    });
  }
);

/**
 * GET /auth/verify
 * トークン検証エンドポイント（API テスト用）
 */
router.get('/verify', (req: Request, res: Response) => {
  const authHeader = req.headers.authorization;
  const token = jwtHandler.extractToken(authHeader);

  if (!token) {
    return res.status(401).json({ error: 'Missing authorization token' });
  }

  const decoded = jwtHandler.verifyToken(token);
  if (!decoded) {
    return res.status(401).json({ error: 'Invalid or expired token' });
  }

  res.json({
    status: 'valid',
    decoded,
  });
});

export default router;
