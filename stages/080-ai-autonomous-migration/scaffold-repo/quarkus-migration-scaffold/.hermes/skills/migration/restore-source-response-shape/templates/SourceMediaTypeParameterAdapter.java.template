package io.rhoai3.migration.response;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;

import org.eclipse.microprofile.config.Config;
import org.eclipse.microprofile.config.ConfigProvider;

import io.quarkus.vertx.http.runtime.filters.Filters;
import io.quarkus.vertx.http.runtime.security.SecurityHandlerPriorities;
import io.vertx.core.http.HttpServerResponse;
import io.vertx.ext.web.RoutingContext;

/**
 * One decided media-type parameter, removed where the source never sent it.
 *
 * <p>Harness capability {@code source-media-type-parameter-adapter/v1} (ADR-019). This file
 * is installed byte-for-byte by the harness and is authorized by its OWN obligation
 * (a Content-Type representation difference), never by a CORS obligation. It carries
 * no application value: the parameter name, the parameter value and the media types
 * come from configuration the harness renders from the recorded difference
 * ({@code rhoai3.source-media-type.*}).
 *
 * <p>It removes exactly that parameter, with exactly that value, from a response of
 * exactly those media types under the application root. Every other parameter, every
 * other media type, the body and its encoding are left as they are. Without complete
 * configuration it registers nothing.
 */
@ApplicationScoped
public class SourceMediaTypeParameterAdapter {

    static final String PREFIX = "rhoai3.source-media-type.";
    static final int PRIORITY = SecurityHandlerPriorities.CORS + 100;
    static final String CONTENT_TYPE = "Content-Type";

    void register(@Observes Filters filters) {
        Config config = ConfigProvider.getConfig();
        String parameter = config.getOptionalValue(PREFIX + "parameter", String.class).orElse("").trim();
        String value = config.getOptionalValue(PREFIX + "parameter-value", String.class).orElse("").trim();
        List<String> types = new ArrayList<>();
        for (String t : config.getOptionalValue(PREFIX + "media-types", String.class).orElse("").split(",")) {
            if (!t.isBlank()) {
                types.add(t.trim().toLowerCase(Locale.ROOT));
            }
        }
        if (parameter.isEmpty() || value.isEmpty() || types.isEmpty()) {
            return;
        }
        String root = config.getOptionalValue("quarkus.http.root-path", String.class).orElse("/");
        String prefix = root.startsWith("/") ? root : "/" + root;
        String base = prefix.endsWith("/") ? prefix.substring(0, prefix.length() - 1) : prefix;
        filters.register(ctx -> {
            String path = ctx.request().path();
            if (base.isEmpty() || (path != null && (path.equals(base) || path.startsWith(base + "/")))) {
                HttpServerResponse response = ctx.response();
                ctx.addHeadersEndHandler(ignored -> rewrite(response, parameter, value, types));
            }
            ctx.next();
        }, PRIORITY);
    }

    static void rewrite(HttpServerResponse response, String parameter, String value, List<String> types) {
        String header = response.headers().get(CONTENT_TYPE);
        if (header == null) {
            return;
        }
        String result = without(header, parameter, value, types);
        if (!result.equals(header)) {
            response.headers().set(CONTENT_TYPE, result);
        }
    }

    /** The header with the decided parameter removed, or the header unchanged. */
    static String without(String header, String parameter, String value, List<String> types) {
        List<String> parts = split(header);
        if (parts.isEmpty() || !types.contains(parts.get(0).trim().toLowerCase(Locale.ROOT))) {
            return header;
        }
        StringBuilder out = new StringBuilder(parts.get(0).trim());
        boolean removed = false;
        for (int i = 1; i < parts.size(); i++) {
            String p = parts.get(i);
            int eq = p.indexOf('=');
            String name = (eq < 0 ? p : p.substring(0, eq)).trim();
            String v = eq < 0 ? "" : p.substring(eq + 1).trim();
            if (v.length() >= 2 && v.startsWith("\"") && v.endsWith("\"")) {
                v = v.substring(1, v.length() - 1);
            }
            if (name.equalsIgnoreCase(parameter) && v.equalsIgnoreCase(value)) {
                removed = true;
                continue;
            }
            out.append(';').append(p);
        }
        return removed ? out.toString() : header;
    }

    /** Split on ';' outside quoted strings. */
    static List<String> split(String header) {
        List<String> out = new ArrayList<>();
        StringBuilder cur = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < header.length(); i++) {
            char c = header.charAt(i);
            if (c == '"') {
                quoted = !quoted;
            }
            if (c == ';' && !quoted) {
                out.add(cur.toString());
                cur.setLength(0);
            } else {
                cur.append(c);
            }
        }
        out.add(cur.toString());
        return out;
    }
}
