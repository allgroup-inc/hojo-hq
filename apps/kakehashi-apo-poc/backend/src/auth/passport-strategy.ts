import passport from 'passport';
import { OIDCStrategy } from 'passport-azure-ad';
import { entraConfig } from '../config/entra-config';

interface UserProfile {
  id: string;
  displayName: string;
  email: string;
  oid: string;
}

const strategy = new OIDCStrategy({
  clientID: entraConfig.clientID,
  clientSecret: entraConfig.clientSecret,
  callbackURL: entraConfig.callbackURL,
  authorizationURL: `${entraConfig.authority}/oauth2/v2.0/authorize`,
  tokenURL: `${entraConfig.authority}/oauth2/v2.0/token`,
  userProfileURL: 'https://graph.microsoft.com/v1.0/me',
  scope: ['profile', 'email', 'openid'],
}, (accessToken: string, refreshToken: string, profile: any, done: any) => {
  // ユーザーオブジェクト作成（DB保存は後の段階）
  const user: UserProfile = {
    id: profile.id,
    displayName: profile.displayName,
    email: profile._json.userPrincipalName,
    oid: profile._json.oid, // Azure Object ID
  };
  done(null, user);
});

passport.use(strategy);
passport.serializeUser((user: any, done: any) => done(null, user));
passport.deserializeUser((user: any, done: any) => done(null, user));

export default passport;
