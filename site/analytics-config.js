/* 計測設定(1箇所)— フクギイロ側で既に決裁・有効化済みのPlausibleアカウントを、
 * 同一ドメイン(allgroup-inc.github.io)配下のページとして共有する。
 * 新規のアカウント作成・決裁は不要(site/fukugiiro/analytics-config.js と同じ設定)。
 */
window.HQ_ANALYTICS = {provider: "plausible", domain: "allgroup-inc.github.io"};
