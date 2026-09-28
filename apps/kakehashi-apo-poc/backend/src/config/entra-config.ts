export const entraConfig = {
  clientID: process.env.ENTRA_CLIENT_ID || '',
  clientSecret: process.env.ENTRA_CLIENT_SECRET || '',
  callbackURL: process.env.ENTRA_CALLBACK_URL || 'http://localhost:3000/auth/callback',
  authority: 'https://login.microsoftonline.com/common',
  discoveryUrl: 'https://login.microsoftonline.com/common/.well-known/openid-configuration',
};
