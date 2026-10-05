package io.rhoai3.migration.response;

import java.net.URI;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.regex.Pattern;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;

import org.eclipse.microprofile.config.Config;
import org.eclipse.microprofile.config.ConfigProvider;

import io.quarkus.vertx.http.runtime.filters.Filters;
import io.quarkus.vertx.http.runtime.security.SecurityHandlerPriorities;
import io.vertx.core.MultiMap;
import io.vertx.core.http.HttpMethod;
import io.vertx.core.http.HttpServerRequest;
import io.vertx.core.http.HttpServerResponse;
import io.vertx.core.net.HostAndPort;
import io.vertx.ext.web.RoutingContext;

/**
 * The SOURCE application's cross-origin behaviour, on this platform's HTTP layer.
 *
 * <p>Harness capability {@code source-cors-response-adapter/v1} (ADR-019). This file is
 * installed byte-for-byte by the harness; it carries no application value. Every
 * permission it can grant comes from configuration the harness renders from the
 * frozen source's own CORS policy ({@code rhoai3.source-cors.*}), and from the
 * request.
 *
 * <p><b>Where it runs.</b> The platform answers a CORS preflight in its own route
 * filter (priority {@link SecurityHandlerPriorities#CORS}) and ends the response
 * there, before authentication, authorization or any application endpoint. A
 * controller-level response filter never sees that response. This adapter is a
 * route filter registered ABOVE the platform's, so it runs first, decides what the
 * source would decide, and reshapes whatever the platform then writes in a
 * headers-end handler -- including the platform's early preflight answer.
 *
 * <p><b>What it never does.</b>
 * <ul>
 *   <li>It never grants what the platform refused: a response the platform did not
 *       mark with {@code Access-Control-Allow-Origin} leaves with no CORS header at
 *       all, and its status is not changed.</li>
 *   <li>It never widens the source policy: an origin, method or header the source
 *       policy does not allow is refused (403, as the source refused it) or simply
 *       not named; a requested header is echoed only when the policy allows it.</li>
 *   <li>A request without {@code Origin} is not touched at all. A same-origin request
 *       is not a CORS request for the source either: the platform's CORS filter does
 *       not judge it, it reaches ordinary routing exactly as without {@code Origin}
 *       (the header is restored after authorization), and it leaves with no CORS
 *       header.</li>
 *   <li>It does not touch {@code Content-Type} or any other response header.</li>
 * </ul>
 *
 * <p><b>Security that precedes CORS in the source.</b> When the rendered policy says
 * the source's security layer ran before its CORS processing, a 401 leaves without
 * CORS headers, a refused cross-origin request is answered after authorization, and
 * -- while the source's security switch is on -- a preflight is authenticated like
 * any other request instead of being answered early.
 */
@ApplicationScoped
public class SourceCorsResponseAdapter {

    static final String PREFIX = "rhoai3.source-cors.";

    /** Runs before the platform's CORS filter, so its headers-end handler wraps the early answer. */
    static final int EARLY_PRIORITY = SecurityHandlerPriorities.CORS + 100;
    /** Runs after the platform's authorization filter and before any route. */
    static final int LATE_PRIORITY = Math.max(1, SecurityHandlerPriorities.AUTHORIZATION / 2);

    static final String ORIGIN = "Origin";
    static final String REQUEST_METHOD = "Access-Control-Request-Method";
    static final String REQUEST_HEADERS = "Access-Control-Request-Headers";
    static final String ALLOW_ORIGIN = "Access-Control-Allow-Origin";
    static final String ALLOW_METHODS = "Access-Control-Allow-Methods";
    static final String ALLOW_HEADERS = "Access-Control-Allow-Headers";
    static final String ALLOW_CREDENTIALS = "Access-Control-Allow-Credentials";
    static final String EXPOSE_HEADERS = "Access-Control-Expose-Headers";
    static final String MAX_AGE = "Access-Control-Max-Age";
    static final List<String> CORS_RESPONSE_HEADERS = List.of(
        ALLOW_ORIGIN, ALLOW_METHODS, ALLOW_HEADERS, ALLOW_CREDENTIALS, EXPOSE_HEADERS, MAX_AGE);
    /** The body the source's CORS processor wrote when it refused a request. */
    static final String REJECTED_BODY = "Invalid CORS request";

    static final String DEFERRED_ORIGIN = "rhoai3.source-cors.deferred-origin";
    static final String DEFERRED_REJECT = "rhoai3.source-cors.deferred-reject";
    static final String ANSWERED = "rhoai3.source-cors.answered";
    static final String SAME_ORIGIN = "rhoai3.source-cors.same-origin";

    void register(@Observes Filters filters) {
        Policy policy = Policy.load(ConfigProvider.getConfig());
        if (policy == null) {
            return;
        }
        filters.register(ctx -> early(policy, ctx), EARLY_PRIORITY);
        filters.register(ctx -> late(policy, ctx), LATE_PRIORITY);
    }

    // ------------------------------------------------------------------ filters

    static void early(Policy policy, RoutingContext ctx) {
        HttpServerRequest request = ctx.request();
        String origin = request.getHeader(ORIGIN);
        if (origin == null) {
            ctx.next();
            return;
        }
        String appPath = policy.applicationPath(request.path());
        if (appPath == null) {
            ctx.next();
            return;
        }
        HttpServerResponse response = ctx.response();
        if (isSameOrigin(request, origin)) {
            // Not a CORS request for the source: it proceeds to ordinary routing exactly
            // as without Origin (ADR-020). The platform's CORS filter would otherwise
            // judge it (a 403 for a method outside its list); hide the header from it
            // and restore it once routing is next.
            ctx.put(SAME_ORIGIN, origin);
            request.headers().remove(ORIGIN);
            ctx.addHeadersEndHandler(ignored -> stripAll(response));
            ctx.next();
            return;
        }
        boolean preflight = isPreflight(request);
        if (preflight && policy.preflightAuthenticated) {
            // The source authenticated a preflight like any other request. Hide the
            // Origin from the platform's early answer so authentication and
            // authorization run; the late filter restores it.
            ctx.put(DEFERRED_ORIGIN, origin);
            request.headers().remove(ORIGIN);
            ctx.addHeadersEndHandler(ignored -> {
                if (!Boolean.TRUE.equals(ctx.get(ANSWERED))) {
                    stripAll(response);
                }
            });
            ctx.next();
            return;
        }
        Decision decision = policy.decide(request, origin, appPath, preflight);
        if (decision.kind == Kind.REJECT) {
            if (!preflight && policy.securityPrecedes) {
                ctx.put(DEFERRED_REJECT, Boolean.TRUE);
            } else {
                reject(response);
                return;
            }
        }
        ctx.addHeadersEndHandler(ignored -> reshape(policy, response, decision, preflight));
        ctx.next();
    }

    static void late(Policy policy, RoutingContext ctx) {
        HttpServerRequest request = ctx.request();
        HttpServerResponse response = ctx.response();
        String sameOrigin = ctx.get(SAME_ORIGIN);
        if (sameOrigin != null) {
            request.headers().set(ORIGIN, sameOrigin);
            ctx.next();
            return;
        }
        String deferred = ctx.get(DEFERRED_ORIGIN);
        if (deferred != null) {
            request.headers().set(ORIGIN, deferred);
            String appPath = policy.applicationPath(request.path());
            Decision decision = policy.decide(request, deferred, appPath, true);
            // the platform's own origin enforcement first, then the source's
            if (decision.kind == Kind.REJECT || !policy.platformAllowsOrigin(deferred)) {
                reject(response);
                return;
            }
            if (decision.kind == Kind.NONE) {
                ctx.next();
                return;
            }
            ctx.put(ANSWERED, Boolean.TRUE);
            write(policy, response, decision, true);
            response.setStatusCode(200).end();
            return;
        }
        if (Boolean.TRUE.equals(ctx.get(DEFERRED_REJECT))) {
            reject(response);
            return;
        }
        ctx.next();
    }

    // ---------------------------------------------------------------- responses

    static void reshape(Policy policy, HttpServerResponse response, Decision decision, boolean preflight) {
        if (policy.securityRejectionsBare && response.getStatusCode() == 401) {
            stripAll(response);
            return;
        }
        boolean granted = response.headers().contains(ALLOW_ORIGIN);
        if (!granted || decision.kind != Kind.ALLOW) {
            stripAll(response);
            return;
        }
        write(policy, response, decision, preflight);
    }

    static void write(Policy policy, HttpServerResponse response, Decision decision, boolean preflight) {
        stripAll(response);
        MultiMap headers = response.headers();
        headers.set(ALLOW_ORIGIN, decision.allowOrigin);
        if (preflight) {
            headers.set(ALLOW_METHODS, String.join(",", decision.allowMethods));
            if (!decision.allowHeaders.isEmpty()) {
                headers.set(ALLOW_HEADERS, String.join(", ", decision.allowHeaders));
            }
            if (decision.rule.maxAge != null) {
                headers.set(MAX_AGE, decision.rule.maxAge);
            }
        }
        if (decision.rule.exposedHeaders != null) {
            headers.set(EXPOSE_HEADERS, decision.rule.exposedHeaders);
        }
        if (decision.rule.allowCredentials) {
            headers.set(ALLOW_CREDENTIALS, "true");
        }
    }

    static void reject(HttpServerResponse response) {
        stripAll(response);
        response.setStatusCode(403).end(REJECTED_BODY);
    }

    static void stripAll(HttpServerResponse response) {
        for (String name : CORS_RESPONSE_HEADERS) {
            response.headers().remove(name);
        }
    }

    // ------------------------------------------------------------------ request

    static boolean isPreflight(HttpServerRequest request) {
        return request.method() == HttpMethod.OPTIONS && request.getHeader(REQUEST_METHOD) != null;
    }

    static boolean isSameOrigin(HttpServerRequest request, String origin) {
        URI uri;
        try {
            uri = URI.create(origin.trim());
        } catch (IllegalArgumentException e) {
            return false;
        }
        if (uri.getScheme() == null || uri.getHost() == null) {
            return false;
        }
        HostAndPort authority = request.authority();
        if (authority == null) {
            return false;
        }
        String scheme = request.scheme() == null ? "http" : request.scheme();
        return uri.getScheme().equalsIgnoreCase(scheme)
            && uri.getHost().equalsIgnoreCase(authority.host())
            && effectivePort(uri.getScheme(), uri.getPort()) == effectivePort(scheme, authority.port());
    }

    static int effectivePort(String scheme, int port) {
        if (port >= 0) {
            return port;
        }
        return "https".equalsIgnoreCase(scheme) ? 443 : 80;
    }

    static List<String> tokens(String value) {
        List<String> out = new ArrayList<>();
        if (value == null) {
            return out;
        }
        for (String part : value.split(",")) {
            String t = part.trim();
            if (!t.isEmpty()) {
                out.add(t);
            }
        }
        return out;
    }

    // ------------------------------------------------------------------- policy

    enum Kind { ALLOW, REJECT, NONE }

    static final class Decision {
        final Kind kind;
        final Rule rule;
        final String allowOrigin;
        final List<String> allowMethods;
        final List<String> allowHeaders;

        Decision(Kind kind, Rule rule, String allowOrigin, List<String> allowMethods, List<String> allowHeaders) {
            this.kind = kind;
            this.rule = rule;
            this.allowOrigin = allowOrigin;
            this.allowMethods = allowMethods;
            this.allowHeaders = allowHeaders;
        }

        static final Decision NONE = new Decision(Kind.NONE, null, null, List.of(), List.of());
        static final Decision REJECT = new Decision(Kind.REJECT, null, null, List.of(), List.of());
    }

    static final class Policy {
        final String rootPath;
        final List<Rule> rules;
        final boolean securityPrecedes;
        final boolean preflightAuthenticated;
        final boolean securityRejectionsBare;
        final boolean platformEnabled;
        final List<String> platformOrigins;

        Policy(String rootPath, List<Rule> rules, boolean securityPrecedes, boolean preflightAuthenticated,
               boolean securityRejectionsBare, boolean platformEnabled, List<String> platformOrigins) {
            this.rootPath = rootPath;
            this.rules = rules;
            this.securityPrecedes = securityPrecedes;
            this.preflightAuthenticated = preflightAuthenticated;
            this.securityRejectionsBare = securityRejectionsBare;
            this.platformEnabled = platformEnabled;
            this.platformOrigins = platformOrigins;
        }

        static Policy load(Config config) {
            int count = config.getOptionalValue(PREFIX + "rule-count", Integer.class).orElse(0);
            if (count <= 0) {
                return null;
            }
            List<Rule> rules = new ArrayList<>();
            for (int i = 0; i < count; i++) {
                rules.add(Rule.load(config, PREFIX + "rule." + i + "."));
            }
            String root = config.getOptionalValue("quarkus.http.root-path", String.class).orElse("/");
            if (!root.startsWith("/")) {
                root = "/" + root;
            }
            if (!root.endsWith("/")) {
                root = root + "/";
            }
            String when = config.getOptionalValue(PREFIX + "preflight-authenticated-when", String.class).orElse("");
            boolean authenticated = false;
            if ("always".equals(when)) {
                authenticated = true;
            } else if (when.contains("=")) {
                String key = when.substring(0, when.indexOf('=')).trim();
                String value = when.substring(when.indexOf('=') + 1).trim();
                authenticated = config.getOptionalValue(key, String.class)
                    .map(v -> v.trim().equalsIgnoreCase(value)).orElse(false);
            }
            boolean precedes = config.getOptionalValue(PREFIX + "security-precedes-cors", Boolean.class).orElse(false);
            boolean bare = config.getOptionalValue(PREFIX + "security-rejections-bare", Boolean.class).orElse(false);
            boolean enabled = config.getOptionalValue("quarkus.http.cors.enabled", Boolean.class).orElse(false);
            List<String> origins = tokens(config.getOptionalValue("quarkus.http.cors.origins", String.class).orElse(""));
            return new Policy(root, Collections.unmodifiableList(rules), precedes || authenticated,
                              authenticated, bare, enabled, origins);
        }

        /** The request path below the application root, or null outside it. */
        String applicationPath(String path) {
            if (path == null) {
                return null;
            }
            if ("/".equals(rootPath)) {
                return path;
            }
            if (path.equals(rootPath.substring(0, rootPath.length() - 1))) {
                return "/";
            }
            if (path.startsWith(rootPath)) {
                return path.substring(rootPath.length() - 1);
            }
            return null;
        }

        /** The platform's own origin setting, as its CORS filter reads it. */
        boolean platformAllowsOrigin(String origin) {
            if (!platformEnabled) {
                return false;
            }
            for (String o : platformOrigins) {
                if ("*".equals(o) || "/.*/".equals(o) || o.equals(origin)) {
                    return true;
                }
                if (o.length() > 2 && o.startsWith("/") && o.endsWith("/")
                    && Pattern.compile(o.substring(1, o.length() - 1)).matcher(origin).matches()) {
                    return true;
                }
            }
            return false;
        }

        Decision decide(HttpServerRequest request, String origin, String appPath, boolean preflight) {
            String method = preflight ? request.getHeader(REQUEST_METHOD).trim().toUpperCase(Locale.ROOT)
                                      : request.method().name();
            Mapping best = null;
            for (Rule rule : rules) {
                for (Mapping m : rule.mappings) {
                    if (m.handles(method) && m.matches(appPath) && (best == null || m.moreSpecificThan(best))) {
                        best = m;
                    }
                }
            }
            if (best == null) {
                return Decision.NONE;
            }
            Rule rule = best.rule;
            String allowOrigin = rule.checkOrigin(origin);
            if (allowOrigin == null) {
                return Decision.REJECT;
            }
            List<String> allowMethods;
            List<String> permitted = rule.methods != null ? rule.methods : best.allowedByDefault();
            if (permitted.contains("*")) {
                allowMethods = List.of(method);
            } else if (permitted.contains(method)) {
                allowMethods = permitted;
            } else {
                return Decision.REJECT;
            }
            List<String> allowHeaders = List.of();
            if (preflight) {
                List<String> requested = tokens(request.getHeader(REQUEST_HEADERS));
                allowHeaders = rule.checkHeaders(requested);
                if (allowHeaders == null) {
                    return Decision.REJECT;
                }
            }
            return new Decision(Kind.ALLOW, rule, allowOrigin, allowMethods, allowHeaders);
        }
    }

    static final class Rule {
        final List<String> origins;
        final List<Pattern> originPatterns;
        final List<String> methods;
        final List<String> headers;
        final String exposedHeaders;
        final String maxAge;
        final boolean allowCredentials;
        final List<Mapping> mappings = new ArrayList<>();

        Rule(List<String> origins, List<Pattern> originPatterns, List<String> methods, List<String> headers,
             String exposedHeaders, String maxAge, boolean allowCredentials) {
            this.origins = origins;
            this.originPatterns = originPatterns;
            this.methods = methods;
            this.headers = headers;
            this.exposedHeaders = exposedHeaders;
            this.maxAge = maxAge;
            this.allowCredentials = allowCredentials;
        }

        static Rule load(Config config, String prefix) {
            List<String> origins = tokens(config.getOptionalValue(prefix + "origins", String.class).orElse(""));
            List<Pattern> patterns = new ArrayList<>();
            for (String p : tokens(config.getOptionalValue(prefix + "origin-patterns", String.class).orElse(""))) {
                patterns.add(originPattern(p));
            }
            Optional<String> methods = config.getOptionalValue(prefix + "methods", String.class);
            List<String> methodList = null;
            if (methods.isPresent()) {
                methodList = new ArrayList<>();
                for (String m : tokens(methods.get())) {
                    methodList.add(m.toUpperCase(Locale.ROOT));
                }
            }
            List<String> headers = tokens(config.getOptionalValue(prefix + "headers", String.class).orElse(""));
            String exposed = config.getOptionalValue(prefix + "exposed-headers", String.class).orElse(null);
            String maxAge = config.getOptionalValue(prefix + "max-age", String.class).orElse(null);
            boolean credentials = config.getOptionalValue(prefix + "allow-credentials", Boolean.class).orElse(false);
            Rule rule = new Rule(origins, patterns, methodList, headers, exposed, maxAge, credentials);
            int count = config.getOptionalValue(prefix + "mapping-count", Integer.class).orElse(0);
            for (int i = 0; i < count; i++) {
                String raw = config.getValue(prefix + "mapping." + i, String.class).trim();
                int space = raw.indexOf(' ');
                String verbs = space < 0 ? "*" : raw.substring(0, space);
                String pattern = space < 0 ? raw : raw.substring(space + 1).trim();
                rule.mappings.add(new Mapping(rule, verbs, pattern));
            }
            return rule;
        }

        static Pattern originPattern(String p) {
            StringBuilder sb = new StringBuilder();
            for (String part : p.split("\\*", -1)) {
                if (sb.length() > 0) {
                    sb.append(".*");
                }
                sb.append(Pattern.quote(part));
            }
            return Pattern.compile(sb.toString(), Pattern.CASE_INSENSITIVE);
        }

        /** The Access-Control-Allow-Origin value the source sent, or null when it refused. */
        String checkOrigin(String requestOrigin) {
            String origin = trimTrailingSlash(requestOrigin.trim());
            if (origins.contains("*") && !allowCredentials) {
                return "*";
            }
            for (String allowed : origins) {
                if (!"*".equals(allowed) && trimTrailingSlash(allowed).equalsIgnoreCase(origin)) {
                    return requestOrigin;
                }
            }
            for (Pattern pattern : originPatterns) {
                if (pattern.matcher(origin).matches()) {
                    return requestOrigin;
                }
            }
            return null;
        }

        /** The requested headers the source allowed; null when none of a non-empty request was allowed. */
        List<String> checkHeaders(List<String> requested) {
            if (requested.isEmpty()) {
                return List.of();
            }
            if (headers.isEmpty()) {
                return null;
            }
            boolean any = headers.contains("*");
            List<String> out = new ArrayList<>();
            for (String h : requested) {
                if (any) {
                    out.add(h);
                    continue;
                }
                for (String allowed : headers) {
                    if (allowed.equalsIgnoreCase(h)) {
                        out.add(h);
                        break;
                    }
                }
            }
            return out.isEmpty() ? null : out;
        }

        static String trimTrailingSlash(String s) {
            return s.endsWith("/") ? s.substring(0, s.length() - 1) : s;
        }
    }

    static final class Mapping {
        static final List<String> DEFAULT_METHODS = List.of("GET", "HEAD", "POST");

        final Rule rule;
        final List<String> verbs;
        final String pattern;
        final String[] segments;
        final Pattern[] compiled;
        final int wildcards;

        Mapping(Rule rule, String verbs, String pattern) {
            this.rule = rule;
            List<String> v = new ArrayList<>();
            if (!"*".equals(verbs)) {
                for (String t : verbs.split("\\|")) {
                    if (!t.isBlank()) {
                        v.add(t.trim().toUpperCase(Locale.ROOT));
                    }
                }
            }
            this.verbs = Collections.unmodifiableList(v);
            this.pattern = pattern.startsWith("/") ? pattern : "/" + pattern;
            this.segments = split(this.pattern);
            this.compiled = new Pattern[segments.length];
            int w = 0;
            for (int i = 0; i < segments.length; i++) {
                if (!"**".equals(segments[i])) {
                    compiled[i] = segmentPattern(segments[i]);
                }
                w += count(segments[i], '*') + count(segments[i], '{') + ("**".equals(segments[i]) ? 10 : 0);
            }
            this.wildcards = w;
        }

        /** The methods a mapping-derived policy allowed: the mapping's own, or the source's default. */
        List<String> allowedByDefault() {
            return verbs.isEmpty() ? DEFAULT_METHODS : verbs;
        }

        boolean handles(String method) {
            return verbs.isEmpty() || verbs.contains(method) || ("HEAD".equals(method) && verbs.contains("GET"));
        }

        boolean matches(String path) {
            if (match(split(path), 0, 0)) {
                return true;
            }
            return path.length() > 1 && path.endsWith("/") && match(split(path.substring(0, path.length() - 1)), 0, 0);
        }

        boolean moreSpecificThan(Mapping other) {
            if (wildcards != other.wildcards) {
                return wildcards < other.wildcards;
            }
            return pattern.length() > other.pattern.length();
        }

        private boolean match(String[] path, int pi, int si) {
            if (pi == segments.length) {
                return si == path.length;
            }
            if ("**".equals(segments[pi])) {
                for (int k = si; k <= path.length; k++) {
                    if (match(path, pi + 1, k)) {
                        return true;
                    }
                }
                return false;
            }
            return si < path.length && compiled[pi].matcher(path[si]).matches() && match(path, pi + 1, si + 1);
        }

        static String[] split(String path) {
            List<String> out = new ArrayList<>(Arrays.asList(path.split("/")));
            out.removeIf(String::isEmpty);
            return out.toArray(new String[0]);
        }

        static int count(String s, char c) {
            int n = 0;
            for (int i = 0; i < s.length(); i++) {
                if (s.charAt(i) == c) {
                    n++;
                }
            }
            return n;
        }

        static Pattern segmentPattern(String segment) {
            StringBuilder sb = new StringBuilder();
            int i = 0;
            while (i < segment.length()) {
                char c = segment.charAt(i);
                if (c == '{') {
                    int depth = 1;
                    int j = i + 1;
                    while (j < segment.length() && depth > 0) {
                        if (segment.charAt(j) == '{') {
                            depth++;
                        } else if (segment.charAt(j) == '}') {
                            depth--;
                        }
                        j++;
                    }
                    String body = segment.substring(i + 1, Math.max(i + 1, j - 1));
                    int colon = body.indexOf(':');
                    sb.append(colon < 0 ? "([^/]+)" : "(" + body.substring(colon + 1) + ")");
                    i = j;
                } else if (c == '*') {
                    sb.append("[^/]*");
                    i++;
                } else if (c == '?') {
                    sb.append("[^/]");
                    i++;
                } else {
                    int j = i;
                    while (j < segment.length() && "{*?".indexOf(segment.charAt(j)) < 0) {
                        j++;
                    }
                    sb.append(Pattern.quote(segment.substring(i, j)));
                    i = j;
                }
            }
            return Pattern.compile(sb.toString());
        }
    }
}
