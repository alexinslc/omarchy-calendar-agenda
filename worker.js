const CLIENT_CONFIG_PATH = "/oauth/client-config";
const HARDENING_HEADERS = {
  "Cache-Control": "no-store",
  "Content-Security-Policy": "default-src 'none'",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
};

function responseHeaders(values = {}) {
  return { ...HARDENING_HEADERS, ...values };
}

function clientConfig(env) {
  if (!env.GOOGLE_OAUTH_CLIENT_ID || !env.GOOGLE_OAUTH_CLIENT_SECRET) {
    return new Response(
      JSON.stringify({ error: "production OAuth configuration is unavailable" }),
      {
        status: 503,
        headers: responseHeaders({
          "Content-Type": "application/json; charset=utf-8",
        }),
      },
    );
  }

  return new Response(
    JSON.stringify({
      schemaVersion: 1,
      google: {
        client_id: env.GOOGLE_OAUTH_CLIENT_ID,
        client_secret: env.GOOGLE_OAUTH_CLIENT_SECRET,
      },
    }),
    {
      headers: responseHeaders({
        "Content-Type": "application/json; charset=utf-8",
      }),
    },
  );
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === CLIENT_CONFIG_PATH) {
      if (request.method !== "GET") {
        return new Response(null, {
          status: 405,
          headers: responseHeaders({ Allow: "GET" }),
        });
      }
      return clientConfig(env);
    }
    return env.ASSETS.fetch(request);
  },
};
