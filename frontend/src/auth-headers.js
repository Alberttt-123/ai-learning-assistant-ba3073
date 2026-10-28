// Nginx may reserve Authorization for its independent Basic authentication.
// Only the explicit deployment meta tag enables the alternate app header.
export function sessionAuthHeaders(token, document = globalThis.document) {
    const proxyMode = document?.querySelector?.('meta[name="aila-session-header"]')?.content;
    const name = proxyMode === "X-App-Authorization" ? proxyMode : "Authorization";
    return { [name]: `Bearer ${token}` };
}
