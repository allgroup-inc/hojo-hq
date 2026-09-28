import passport from 'passport';
import { OIDCStrategy, IProfile } from 'passport-azure-ad';
import { entraConfig } from '../config/entra-config';

export interface UserProfile {
  id: string;
  displayName: string;
  email: string;
  oid: string;
}

export function initializePassportStrategy(): void {
  // Only initialize if clientID and clientSecret are provided
  if (!entraConfig.clientID || !entraConfig.clientSecret) {
    console.warn('Warning: Entra ID credentials not configured. Skipping Passport strategy initialization.');
    return;
  }

  const strategy = new OIDCStrategy({
    identityMetadata: entraConfig.identityMetadata,
    clientID: entraConfig.clientID,
    clientSecret: entraConfig.clientSecret,
    redirectUrl: entraConfig.redirectUrl,
    responseType: 'code',
    responseMode: 'query',
    passReqToCallback: false,
    scope: ['profile', 'email', 'openid'],
  }, (iss: string, sub: string, profile: IProfile, accessToken: string, refreshToken: string, done: any) => {
    // ユーザーオブジェクト作成（DB保存は後の段階）
    const user: UserProfile = {
      id: profile.oid || sub,
      displayName: profile.displayName || '',
      email: profile.upn || '',
      oid: profile.oid || '',
    };
    done(null, user);
  });

  passport.use(strategy);
}

passport.serializeUser((user: any, done: any) => done(null, user));
passport.deserializeUser((user: any, done: any) => done(null, user));

export default passport;
